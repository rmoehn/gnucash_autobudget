# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import os
import tempfile
from unittest import TestCase

from gnucash import Session, Account
import gnucash.gnucash_core_c as gc

from gnucash_autobudget import core as mut


def new_account(book, name, acct_type, children=None):
    acct = Account(book)
    acct.SetName(name)
    acct.SetType(acct_type)
    for c in children or []:
        acct.append_child(c)

    return acct


class TestEnsureAccountPresent(TestCase):
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
        s = Session(b"xml://{}".format(self._session_file_name),
                               is_new=True)
        self.session = s

        self.root_account \
            = new_account(s.book, b"Root", gc.ACCT_TYPE_ROOT,
                  [new_account(s.book, b"Expenses", gc.ACCT_TYPE_EXPENSE),
                   new_account(s.book, b"Budget", gc.ACCT_TYPE_ASSET,
                       [new_account(s.book, b"Budgeted Funds",
                                    gc.ACCT_TYPE_LIABILITY),
                        new_account(s.book, b"Available to Budget",
                                    gc.ACCT_TYPE_ASSET)])])


    def tearDown(self):
        self.session.end()
        self.session.destroy()


    def test_all_there(self):
        mut._ensure_mandatory_structure(self.root_account)
