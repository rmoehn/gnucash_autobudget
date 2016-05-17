# -*- coding: utf-8 -*-
# pylint: disable=protected-access

# Note: No unicode literals, because the GnuCash Python bindings don't like
# unicode.

import os
import tempfile
from unittest import TestCase

from gnucash import Session, Account
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
        _session_file_handle, cls._session_file_name \
            = tempfile.mkstemp(suffix=".xac")
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


#### A helper procedure

def account(book, name, acct_type, children=None):
    acct = Account(book)
    acct.SetName(name)
    acct.SetType(acct_type)
    for c in children or []:
        acct.append_child(c)

    return acct


#### Class for testing _ensure_mandatory_structure()

# Make the following code more readable.
ASSET = gc.ACCT_TYPE_ASSET
EQUITY = gc.ACCT_TYPE_EQUITY
EXPENSE = gc.ACCT_TYPE_EXPENSE
LIABILITY = gc.ACCT_TYPE_LIABILITY
ROOT = gc.ACCT_TYPE_ROOT

class TestEnsureMandatoryStructure(SessionTestCase):
    def test_all_proper(self):
        book = self.session.book # Just to make the following shorter.

        mut._ensure_mandatory_structure(
            account(book, "Root", ROOT,
                [account(book, "Expenses", EXPENSE),
                 account(book, "Budget", ASSET,
                     [account(book, "Budgeted Funds", LIABILITY),
                      account(book, "Available to Budget", ASSET)])]))


    def test_additional_accounts_ok(self):
        book = self.session.book # Just to make the following shorter.

        mut._ensure_mandatory_structure(
            account(book, "Root", ROOT,
                [account(book, "Starting Balance", EQUITY),
                 account(book, "Expenses", EXPENSE,
                     [account(book, "Everyday", EXPENSE,
                         [account(book, "Groceries", EXPENSE)])]),
                 account(book, "Budget", ASSET,
                     [account(book, "Budgeted Funds", LIABILITY),
                      account(book, "Available to Budget", ASSET)])]))


    def test_wrong_type(self):
        book = self.session.book # Just to make the following shorter.

        with self.assertRaises(mut.InputException):
            mut._ensure_mandatory_structure(
                account(book, "Root", ROOT,
                    [account(book, "Expenses", EXPENSE),
                     account(book, "Budget", ASSET,
                         [account(book, "Budgeted Funds", LIABILITY),
                          account(book, "Available to Budget", LIABILITY)])]))


    def test_acc_missing(self):
        book = self.session.book # Just to make the following shorter.

        with self.assertRaises(mut.InputException):
            mut._ensure_mandatory_structure(
                account(book, "Root", ROOT,
                    [account(book, "Expenses", EXPENSE),
                     account(book, "Budget", ASSET,
                         [account(book, "Available to Budget", ASSET)])]))
