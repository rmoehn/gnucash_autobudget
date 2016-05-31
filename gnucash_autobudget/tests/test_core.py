# -*- coding: utf-8 -*-
# pylint: disable=protected-access

# Note: No unicode literals, because the GnuCash Python bindings don't like
# unicode.

from functools import partial
import os
import tempfile
from unittest import TestCase

from gnucash import Account, GncNumeric, Session, Split, Transaction
import gnucash.gnucash_core_c as gc

from gnucash_autobudget import core as mut

#### Custom TestCase

class SessionTestCase(TestCase):
    """
    A :py:class:`TestCase` providing :py:class:`gnucash.Session` setup and teardown.
    """

    # Note: I suspect that creating and deleting a temporary file for every test
    # method would be too much. We're not writing to it anyway. This is why I
    # implement this as a setUpClass(). If you have a different opinion, tell
    # me.
    @classmethod
    def setUpClass(cls):
        # TODO: Need to use a temporary directory!
        _session_file_handle, cls._session_file_name \
            = tempfile.mkstemp(suffix=".gnucash")
        os.close(_session_file_handle)

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls._session_file_name)

    def setUp(self):
        self.session = Session("xml://{}".format(self._session_file_name),
                               is_new=True)

    def tearDown(self):
        self.session.end()
        self.session.destroy()


#### Helper procedures

def new_account(book, name, acct_type, children=None, is_placeholder=False):
    acct = Account(book)
    acct.SetName(name)
    if name == 'Root':
        book.set_root_account(acct)
    else:
        acct.SetCommodity(book.get_table().lookup('CURRENCY', 'EUR'))

    acct.SetType(acct_type)
    acct.SetPlaceholder(is_placeholder)
    for c in children or []:
        acct.append_child(c)

    return acct


def new_split(book, account_nm, value):
    if not isinstance(value, int):
        raise NotImplementedError("This only handles ints. You provided {}."\
                                      .format(value))

    if value >= 0:
        num = GncNumeric(value, 1)
    else:
        num = GncNumeric(-value, 1).neg()

    s = Split(book)
    s.SetValue(num)
    s.SetAccount(book.get_root_account().lookup_by_full_name(account_nm))
    return s


def new_transaction(book, description, entries):
    t = Transaction(book)
    splits = [new_split(book, account_nm, value)
                  for account_nm, value in entries]

    t.BeginEdit()
    t.SetCurrency(book.get_table().lookup('CURRENCY', 'EUR'))
    t.SetDescription(description)
    for s in splits:
        s.SetParent(t)
    t.CommitEdit()

    return t


#### Class for testing _ensure_mandatory_structure()

# Make the following code more readable.
ASSET = gc.ACCT_TYPE_ASSET
EQUITY = gc.ACCT_TYPE_EQUITY
EXPENSE = gc.ACCT_TYPE_EXPENSE
LIABILITY = gc.ACCT_TYPE_LIABILITY
ROOT = gc.ACCT_TYPE_ROOT

class TestEnsureMandatoryStructure(SessionTestCase):
    def test_all_proper(self):
        account = partial(new_account, self.session.book)

        mut._ensure_mandatory_structure(
            account("Root", ROOT,
                [account("Expenses", EXPENSE),
                 account("Budget", ASSET,
                     [account("Budgeted Funds", LIABILITY),
                      account("Available to Budget", ASSET)])]))


    def test_additional_accounts_ok(self):
        account = partial(new_account, self.session.book)

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
        account = partial(new_account, self.session.book)

        with self.assertRaises(mut.InputException):
            mut._ensure_mandatory_structure(
                account("Root", ROOT,
                    [account("Expenses", EXPENSE),
                     account("Budget", ASSET,
                         [account("Budgeted Funds", LIABILITY),
                          account("Available to Budget", LIABILITY)])]))


    def test_acc_missing(self):
        account = partial(new_account, self.session.book)

        with self.assertRaises(mut.InputException):
            mut._ensure_mandatory_structure(
                account("Root", ROOT,
                    [account("Expenses", EXPENSE),
                     account("Budget", ASSET,
                         [account("Available to Budget", ASSET)])]))


#### Class for testing _expense_to_budget_matching

class TestExpenseToBudgetMatching(SessionTestCase):
    def test_readme_example(self):
        account  = partial(new_account, self.session.book)
        paccount = partial(new_account, self.session.book, is_placeholder=True)

        matching = mut._expense_to_budget_matching(
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
        account  = partial(new_account, self.session.book)
        paccount = partial(new_account, self.session.book, is_placeholder=True)

        matching = mut._expense_to_budget_matching(
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

class TestExpenseToBudgetSplitMatching(SessionTestCase):
    def setUp(self):
        super(TestExpenseToBudgetSplitMatching, self).setUp()
        account  = partial(new_account, self.session.book)
        paccount = partial(new_account, self.session.book, is_placeholder=True)

        self.root_account = account("Root", ROOT,
                                [paccount("Assets", ASSET,
                                     [account("Cash", ASSET)]),
                                 account("Expenses", EXPENSE,
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
                                          [account("Rent", ASSET)])])])

    def test_easiest_trx(self):
        self.assertEqual(
            {},
            mut._expense_to_budget_split_matching(
                new_transaction(self.session.book,
                                "weekly shopping",
                                [("Expenses.Everyday.Groceries", 100),
                                 ("Assets.Cash", -100)]),
                self.session.book.get_root_account(),
                mut._expense_to_budget_matching(self.session.book.get_root_account())))

