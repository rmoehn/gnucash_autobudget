#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Credits: https://github.com/hjacobs/gnucash-fiximports/blob/master/fiximports.py

from __future__ import print_function, unicode_literals

import re
import textwrap

import gnucash.gnucash_core_c as gc

# What do I have to do?
# - Find a matching from Expenses accounts to corresponding Budget accounts.
# - Look at every Expenses account.
# - Find all transactions that don't have a budget entry and whose date is on or
#   after the start date.
# - For each such transaction.
# - Find the expense entries.
# - Generate an entry for Budgeted Funds and the corresponding budget account.
# - Add them to the transaction. ← Only non-functional step.

def paragraphs(u):
    """
    Makes strings from triple-quoted string literals usable.

    See https://archive.org/details/paragraphs_201602 or
    https://gist.github.com/rmoehn/acecb206d44af2053364.
    """

    assert isinstance(u, unicode)

    masked        = re.sub(r"\a\n", "\x01", u)
    stripped      = masked.rstrip().lstrip('\n')
    dedented      = textwrap.dedent(stripped)
    normal_ns     = re.sub(r"\n{2,}", "\n\n", dedented)
    spaces_for_ns = re.sub(r"(?<! \n ) \n (?! \n )",
                               # Matches only solitary newlines.
                           " ",
                           normal_ns,
                           flags=re.X)
    return re.sub(r"\x01", "\n", spaces_for_ns)


class InputException(Exception):
    """
    An exception to be raised when the user provided unsuitable input
    """
    pass


def _ensure_account_present(root_account, acc_name, acc_type):
    acc_type2const = {'asset':     gc.ACCT_TYPE_ASSET,
                      'expense':   gc.ACCT_TYPE_EXPENSE,
                      'liability': gc.ACCT_TYPE_LIABILITY,}

    account = root_account.lookup_by_full_name(acc_name)
    if not (account and account.GetType() == acc_type2const[acc_type]):
        raise InputException(paragraphs("""
            The GnuCash file you provided does not define an {acc_type} account
            named '{name}', but it is required for GnuCash Autocomplete to work.
            """.format(type=acc_type, name=acc_name.replace('.', ':'))))


def _ensure_mandatory_structure(root_account):
    _ensure_account_present(root_account, "Expenses", 'expense')
    _ensure_account_present(root_account, "Budget", 'asset')
    _ensure_account_present(root_account, "Budget.Budgeted Funds", 'liability')
    _ensure_account_present(root_account, "Budget.Available to Budget", 'asset')


def _expense_to_budget_matching(root_account):
    budget_accs  = [a for a in
                       root_account.lookup_by_name("Budget").get_descendants()
                       if a.get_full_name() not in
                           {"Budget.Budgeted Funds",
                            "Budget.Available to Budget"}]
    budget2expense = {a: re.sub(r"\ABudget", "Expenses", a)
                          for a in budget_accs}
    return {e: b for b, e in enumerate(budget2expense) if
                root_account.root_account.lookup_by_full_name(e)}



def add_budget_entries(session, start_date=None):
    root_account = session.book.get_root_account()
    _ensure_mandatory_structure(root_account)
    account_matching = _expense_to_budget_matching(root_account)

