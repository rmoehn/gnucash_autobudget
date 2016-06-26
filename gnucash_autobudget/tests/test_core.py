# -*- coding: utf-8 -*-
# pylint: disable=protected-access

# Note: No unicode literals, because the GnuCash Python bindings don't like
# unicode.

from functools import partial
import os
import shutil
import tempfile
from unittest import TestCase

from gnucash import Account, GncNumeric, Session, Split, Transaction
import gnucash.gnucash_core_c as gc

from gnucash_autobudget import core as mut

#### Custom TestCase

def guid_map(gc_obj_mapping):
    return {k.GetGUID().to_string(): v.GetGUID().to_string()
                for k, v in gc_obj_mapping.items()}

class SessionTestCase(TestCase):
    """
    A :py:class:`TestCase` providing :py:class:`gnucash.Session` setup and teardown.
    """

    ### Setup and teardown

    # Note: I suspect that creating and deleting a temporary file for every test
    # method would be too much. We're not writing to it anyway. This is why I
    # implement this as a setUpClass(). If you have a different opinion, tell
    # me.
    @classmethod
    def setUpClass(cls):
        # TODO: Need to use a temporary directory!
        cls._session_dir_path = tempfile.mkdtemp(prefix="gcabtmp")
        _session_file_handle, cls._session_file_name \
            = tempfile.mkstemp(suffix=".gnucash", dir=cls._session_dir_path)
        os.close(_session_file_handle)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._session_dir_path)

    def setUp(self):
        self.session = Session("xml://{}".format(self._session_file_name),
                               is_new=True)

    def tearDown(self):
        self.session.end()
        self.session.destroy()


    ### Extra assertions

    def assertGUIDMapsEqual(self, matching1, matching2):
        return self.assertEqual(guid_map(matching1), guid_map(matching2))


    ### Convenience constructors

    def new_account(self, name, acct_type, children=None, is_placeholder=False):
        acct = Account(self.session.book)
        acct.SetName(name)
        if name == 'Root':
            self.session.book.set_root_account(acct)
        else:
            acct.SetCommodity(self.session.book.get_table().lookup('CURRENCY',
                                                                   'EUR'))

        acct.SetType(acct_type)
        acct.SetPlaceholder(is_placeholder)
        for c in children or []:
            acct.append_child(c)

        return acct


    def new_split(self, account_nm, value):
        if not isinstance(value, int):
            raise NotImplementedError("This only handles ints. You provided {}."\
                                        .format(value))

        if value >= 0:
            num = GncNumeric(value, 1)
        else:
            num = GncNumeric(-value, 1).neg()

        s = Split(self.session.book)
        s.SetValue(num)
        s.SetAccount(self.session.book.get_root_account()
                                      .lookup_by_full_name(account_nm))
        return s


    def new_transaction(self, description, splits):
        t = Transaction(self.session.book)

        t.BeginEdit()
        t.SetCurrency(self.session.book.get_table().lookup('CURRENCY', 'EUR'))
        t.SetDescription(description)
        for s in splits:
            s.SetParent(t)
        t.CommitEdit()

        return t



    def __init__(self, *args, **kwargs):
        super(SessionTestCase, self).__init__(*args, **kwargs)

        # Partially applied convenience constructors
        self.paccount = partial(self.new_account, is_placeholder=True)


#### Class for testing _ensure_mandatory_structure()

# Make the following code more readable.
ASSET = gc.ACCT_TYPE_ASSET
EQUITY = gc.ACCT_TYPE_EQUITY
EXPENSE = gc.ACCT_TYPE_EXPENSE
LIABILITY = gc.ACCT_TYPE_LIABILITY
ROOT = gc.ACCT_TYPE_ROOT

# REFACTOR: Move the partials out. (RM 2016-05-29)
class TestEnsureMandatoryStructure(SessionTestCase):
    def test_all_proper(self):
        account = self.new_account

        mut._ensure_mandatory_structure(
            account("Root", ROOT,
                [account("Expenses", EXPENSE),
                 account("Budget", ASSET,
                     [account("Budgeted Funds", LIABILITY),
                      account("Available to Budget", ASSET)])]))


    def test_additional_accounts_ok(self):
        account = self.new_account

        mut._ensure_mandatory_structure(
            account("Root", ROOT,
                [account("Starting Balance", EQUITY),
                 account("Expenses", EXPENSE,
                     [account("Everyday", EXPENSE,
                         [account("Groceries", EXPENSE)])]),
                 account("Budget", ASSET,
                     [account("Budgeted Funds", LIABILITY),
                      account("Available to Budget", ASSET)])]))


    def test_wrong_type(self):
        account = self.new_account

        with self.assertRaises(mut.InputException):
            mut._ensure_mandatory_structure(
                account("Root", ROOT,
                    [account("Expenses", EXPENSE),
                     account("Budget", ASSET,
                         [account("Budgeted Funds", LIABILITY),
                          account("Available to Budget", LIABILITY)])]))


    def test_acc_missing(self):
        account = self.new_account

        with self.assertRaises(mut.InputException):
            mut._ensure_mandatory_structure(
                account("Root", ROOT,
                    [account("Expenses", EXPENSE),
                     account("Budget", ASSET,
                         [account("Available to Budget", ASSET)])]))


#### Class for testing _expense_to_budget_matching

class TestExpenseToBudgetMatching(SessionTestCase):
    def test_readme_example(self):
        account  = self.new_account
        paccount = self.paccount

        matching = mut.ExpenseToBudgetAccountMatching(
                       account("Root", ROOT,
                           [account("Expenses", EXPENSE,
                                [paccount("Everyday", EXPENSE,
                                     [account("Groceries", EXPENSE),
                                      account("Beer", EXPENSE),
                                      account("Transportation", EXPENSE)]),
                                 paccount("Monthly", EXPENSE,
                                     [account("Rent", EXPENSE)])]),
                            account("Budget", ASSET,
                                [account("Budgeted Funds", LIABILITY),
                                 account("Available to Budget", ASSET),
                                 paccount("Everyday", ASSET,
                                     [account("Groceries", ASSET),
                                      account("Transportation", ASSET)]),
                                 paccount("Monthly", ASSET,
                                     [account("Rent", ASSET)])])]))

        self.assertEqual(
            {"Expenses.Everyday.Groceries":      "Budget.Everyday.Groceries",
             "Expenses.Everyday.Transportation": "Budget.Everyday.Transportation",
             "Expenses.Monthly.Rent":            "Budget.Monthly.Rent",},
            {ea.get_full_name(): ba.get_full_name()
                for ea, ba in matching.items()})


    def test_wrong_types_extra_budget(self):
        account  = self.new_account
        paccount = self.paccount

        matching = mut.ExpenseToBudgetAccountMatching(
                       account("Root", ROOT,
                           [account("Expenses", EXPENSE,
                                [paccount("Everyday", EXPENSE,
                                     [account("Groceries", EXPENSE),
                                      account("Beer", EXPENSE),
                                      account("Transportation", LIABILITY)]),
                                 paccount("Monthly", EXPENSE,
                                     [account("Rent", EXPENSE)])]),
                            account("Budget", ASSET,
                                [account("Budgeted Funds", LIABILITY),
                                 account("Available to Budget", ASSET),
                                 paccount("Everyday", ASSET,
                                     [account("Groceries", ASSET),
                                      account("Transportation", ASSET)]),
                                 paccount("Monthly", ASSET,
                                     [account("Rent", EQUITY),
                                      account("Sunscreen", ASSET)])])]))

        self.assertEqual(
            {"Expenses.Everyday.Groceries":      "Budget.Everyday.Groceries",},
            {ea.get_full_name(): ba.get_full_name()
                for ea, ba in matching.items()})


#### Class for testing _expense_to_budget_split_matching

# The following transactions are supposed to be the same as in the README. See
# there for a neater presentation.
class TestExpenseToBudgetSplitMatching(SessionTestCase):
    def setUp(self):
        super(TestExpenseToBudgetSplitMatching, self).setUp()
        account  = self.new_account
        paccount = self.paccount

        self.root_account = account("Root", ROOT,
                                [paccount("Assets", ASSET,
                                     [account("Cash", ASSET)]),
                                 account("Expenses", EXPENSE,
                                     [paccount("Everyday", EXPENSE,
                                          [account("Groceries", EXPENSE),
                                           account("Food", EXPENSE),
                                           account("Drink", EXPENSE),
                                           account("Beer", EXPENSE),
                                           account("Transportation", EXPENSE)]),
                                      paccount("Monthly", EXPENSE,
                                          [account("Rent", EXPENSE)])]),
                                 account("Budget", ASSET,
                                     [account("Budgeted Funds", LIABILITY),
                                      account("Available to Budget", ASSET),
                                      paccount("Everyday", ASSET,
                                          [account("Groceries", ASSET),
                                           account("Food", ASSET),
                                           account("Drink", ASSET),
                                           account("Transportation", ASSET)]),
                                      paccount("Monthly", ASSET,
                                          [account("Rent", ASSET)])])])

    def test_easiest_trx(self):
        split = self.new_split

        self.assertGUIDMapsEqual(
            {},
            mut.ExpenseToBudgetSplitMatching(
                self.new_transaction("weekly shopping",
                    [split("Expenses.Everyday.Groceries", 100),
                     split("Assets.Cash",                      -100)])))

        egsplit = split("Expenses.Everyday.Groceries", 100)
        acsplit = split("Assets.Cash",                      -100)
        bbsplit = split("Budget.Budgeted Funds",       100)
        bgsplit = split("Budget.Everyday.Groceries",        -100)
        self.assertGUIDMapsEqual(
            {egsplit: bgsplit},
            mut.ExpenseToBudgetSplitMatching(
                self.new_transaction(
                    "weekly shopping",
                    [egsplit, acsplit, bbsplit, bgsplit])))


    def test_multisplit_trx(self):
        split = self.new_split

        efsplit = split("Expenses.Everyday.Food",  100)
        edsplit = split("Expenses.Everyday.Drink", 100)
        acsplit = split("Assets.Cash",                  -200)
        bbsplit = split("Budget.Budgeted Funds",   100)
        bfsplit = split("Budget.Everyday.Food",         -100)
        self.assertGUIDMapsEqual(
            {efsplit: bfsplit},
            mut.ExpenseToBudgetSplitMatching(
                self.new_transaction(
                    "weekly shopping drink not yet budgeted",
                    [efsplit, edsplit, acsplit, bbsplit, bfsplit])))

        bbsplit = split("Budget.Budgeted Funds",   200)
        bdsplit = split("Budget.Everyday.Drink",        -100)
        self.assertGUIDMapsEqual(
            {efsplit: bfsplit,
             edsplit: bdsplit},
            mut.ExpenseToBudgetSplitMatching(
                self.new_transaction(
                    "weekly shopping drink not yet budgeted",
                    [efsplit, edsplit, acsplit, bbsplit, bfsplit, bdsplit])))


    def test_refund_trx(self):
        split = self.new_split

        acsplit = split("Assets.Cash",            5)
        efsplit = split("Expenses.Everyday.Food",      -5)
        bfsplit = split("Budget.Everyday.Food",   5)
        bbsplit = split("Budget.Budgeted Funds",       -5)
        self.assertGUIDMapsEqual(
            {efsplit: bfsplit},
            mut.ExpenseToBudgetSplitMatching(
                self.new_transaction(
                    "got back some money",
                    [acsplit, efsplit, bfsplit, bbsplit])))
