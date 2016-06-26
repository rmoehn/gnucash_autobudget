# -*- coding: utf-8 -*-

# Note: No unicode literals, because the GnuCash Python bindings don't like
# unicode.

# Credits: https://github.com/hjacobs/gnucash-fiximports/blob/master/fiximports.py

import collections
from datetime import date
import re
import textwrap

from gnucash import Account, Session, Split, Transaction
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

# TODO: Make sure that we're adding transactions in the right currency.

def _paragraphs(u):
    """
    Makes strings from triple-quoted string literals usable.

    See https://archive.org/details/paragraphs_201602 or
    https://gist.github.com/rmoehn/acecb206d44af2053364.
    """

    assert isinstance(u, str)

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


def _stringify_split(s):
    return "{acc:45} {debit:>10} {credit:>10}".format(
               acc=s.GetAccount().get_full_name(),
               debit  = s.GetAmount().reduce().to_string()
                            if s.GetAmount().positive_p()
                            else "",
               credit = s.GetAmount().neg().reduce().to_string()
                            if s.GetAmount().negative_p()
                            else "")


def _stringify_trx(t):
    splits = '\n'.join(["  " + _stringify_split(s) for s in t.GetSplitList()])
    return "{time} {descr}\n{splits}".format(
               time=date.fromtimestamp(t.GetDate()),
               descr=t.GetDescription(),
               splits=splits)


def _root_account(o):
    if isinstance(o, Session):
        return o.book.get_root_account()
    elif isinstance(o, Account):
        return o.get_root()
    elif isinstance(o, Transaction):
        splits = o.GetSplitList()
        if splits:
            return _root_account(splits[0].GetAccount())
        else:
            raise ValueError(
                "This transaction has no Splits and therefore no account and"
                " therefore no root account: {}".format(_stringify_trx(o)))
    elif isinstance(o, Split):
        return _root_account(o.GetAccount())
    else:
        raise TypeError(
            "Cannot find root account for this object: {}".format(o))


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
        raise InputException(_paragraphs("""
            The GnuCash file you provided does not define an {acc_type} account
            named '{name}', but it is required for GnuCash Autocomplete to work.
            """.format(acc_type=acc_type, name=acc_name.replace('.', ':'))))


def _ensure_mandatory_structure(root_account):
    _ensure_account_present(root_account, "Expenses", 'expense')
    _ensure_account_present(root_account, "Budget", 'asset')
    _ensure_account_present(root_account, "Budget.Budgeted Funds", 'liability')
    _ensure_account_present(root_account, "Budget.Available to Budget", 'asset')


def _is_regular_budget_acc(acc):
    return acc.get_full_name() not in {"Budget.Budgeted Funds",
                                       "Budget.Available to Budget"} \
               and not acc.GetPlaceholder() \
               and acc.GetType() == gc.ACCT_TYPE_ASSET


def _is_regular_expense_acc(acc):
    return not acc.GetPlaceholder() and acc.GetType() == gc.ACCT_TYPE_EXPENSE


def _expense_to_budget_matching(root_account):
    budget_accs  = [a for a in
                       root_account.lookup_by_name("Budget").get_descendants()
                       if _is_regular_budget_acc(a)]
    budget2expense = {ba: root_account.lookup_by_full_name(
                              re.sub(r"\ABudget", "Expenses",
                                     ba.get_full_name()))
                          for ba in budget_accs}
    return {e.get_full_name(): b.get_full_name()
                 for b, e in budget2expense.items()
                 if e and _is_regular_expense_acc(e)}


class AccountMatchingIterator(collections.Iterator):
    def __init__(self, account_matching):
        self.account_matching = account_matching
        self.am_iter = account_matching.matching.__iter__()


    def next(self):
        # pylint: disable=protected-access
        return self.account_matching.root_account.lookup_by_full_name(
                    self.am_iter.next())


class ExpenseToBudgetAccountMatching(collections.Mapping):
    def __init__(self, root_account):
        self.root_account = root_account
        self.matching     = _expense_to_budget_matching(root_account)


    def __getitem__(self, key):
        if isinstance(key, str):
            return self.root_account.lookup_by_full_name(self.matching[key])
        elif isinstance(key, Account):
            return self.__getitem__(key.get_full_name())
        else:
            raise TypeError("Can only look up str and Account key in"
                            " ExpenseToBudgetAccountMatching. {} doesn't work."\
                                .format(key))


    def __iter__(self):
        return AccountMatchingIterator(self)


    def __len__(self):
        return self.matching.__len__()




# Hm, which transactions to we want to add to?
# - If the transaction has a Split on an expense account, but no Split on the
#   corresponding budget account.
#
# Which transactions do we not want to add to?
# - If the transaction has a Split on an expense account and a Split of opposite
#   amount on the corresponding budget account.
#
# Which transactions are doubtful?
# - If the transaction has a Split on an expense account and a Split of
#   different amount on the corresponding budget account.
# - If the transaction has a Split on an expense account and a Split on a
#   non-corresponding budget account.


def _trxs_for_budget(account_matching, start_date):
    return {s.parent for s in ea.GetSplitList()
                     for ea in account_matching.keys()
                     if date.fromtimestamp(t.GetDate()) >= start_date}


def _is_expense_split(s):
    return _is_regular_expense_acc(s.GetAccount()) \
               and s.GetAccount().HasAncestor(
                       _root_account(s).lookup_by_name('Expenses'))


def _is_budget_split(s):
    return _is_regular_budget_acc(s.GetAccount()) \
               and s.GetAccount().HasAncestor(
                       _root_account(s).lookup_by_name('Budget'))


def _expense_to_budget_split_matching(t):
    account_matching = ExpenseToBudgetAccountMatching(_root_account(t))
    print {ea.get_full_name(): ba.get_full_name() for ea, ba in
            account_matching.items()}
    print account_matching
    split_list = t.GetSplitList()
    expense_splits = {s for s in split_list
                        if _is_expense_split(s)}
    budget_splits  = {s for s in split_list
                        if _is_budget_split(s)}

    # Note: You might think that a map comprehension would be better and more
    # functional here, but it doesn't work. There might be transactions with
    # multiple splits having the same amount and budget account. If we didn't
    # remove them from the list of available budget splits, two expense splits
    # might end up matched to the same budget split:
    #
    #     es1 = Expenses:Everyday:Food   4
    #     es2 = Expenses:Everyday:Food   4
    #     bs1 = Budget:Everyday:Food        4
    #     bs2 = Budget:Everyday:Food        4
    #
    #     Matching: es1 → bs1, es2 → bs1
    #
    # I almost used a reduce() with Pyrsistent data structures here, but I
    # shouldn't try to be too sophisticated for this small project.
    es2bs = {}
    for es in expense_splits:
        print _stringify_split(es)
        bs = next((bs for bs in budget_splits
                      if bs.GetAmount().equal(es.GetAmount().neg())
                          and bs.GetAccount() == account_matching[es.GetAccount()]),
                  None)
        if bs:
            es2bs[es] = bs
            budget_splits.remove(bs)

    return es2bs


def _matching_budget_split(t, s):
    corresp_acc_splits = {cas for cas in t.GetSplitList()
                              if cas.GetAccount() ==
                                  _expense_to_budget_matching(s.GetAccount())}


# What is a good way to determine unmatched splits?
#
#  - Matched and unmatched Splits are always expense Splits.
#  - An unmatched Split is one that is in the set of matched Splits.
#  - A matched Split is a Split for which we can find a budget Split with a
#    parallel account that doesn't belong to any other matched Split.
def _unmatched_splits(t):
    return {s for s in t.GetSplitList()
              if s.GetAccount().HasAncestor(
                     root_account.lookup_by_name("Expenses"))
                  and not _matching_budget_split(t, s)}


def _unbalanced_splits(t):
    return {s for s in t.GetSplitList()
              if s.GetAccount().HasAncestor(
                     root_account.lookup_by_name("Budget"))
                  and _is_regular_budget_acc(s.GetAccount())
                  and not _matching_expense_split(t, s)}



# Matched Splits are expense Splits for which a budget Split with the same
# amount and parallel account exists.
#
# Basic functionality:
#  - We find unmatched expense Splits and add matching budget Splits. We can
#    only add a matching budget Split if there is a parallel budget account for
#    the expense account of the unmatched Split.
#  - We check if the sum of the amounts of the expense splits matches the sum of
#    the amounts of the budget Splits.
#
# Everything else will catch more errors, but will also not understand manual
# adjustments. For example, if the money for two expense accounts was budgeted
# on a single budget account, I'd have to adjust the transaction manually, but
# GnuCash Autobudget wouldn't know how to deal with that and warn about
# imbalances.
def _add_budget_entries(t):
    for s in _unmatched_splits(t):
        if s.GetAccount() in account_matching:
            _add_splits(t, _budget_splits(s))
        else:
            _logger.info("Transaction %s: No budget account matching %s.",
                 _stringify_trx(t), s.GetAccount())

    for s in _unbalanced_splits(t):
        _logger.warn("Transaction %s: Existing budget entry %s doesn't match"
                     " any expense entry.")


def add_budget_entries(session, start_date=None):
    root_account = _root_account(session)
    _ensure_mandatory_structure(root_account)

    for t in _trxs_for_budget(account_matching, start_date):
        t.BeginEdit()
        _add_budget_entries(t)
        _combine_budget_funds_entries(t)
        _ensure_sanity(t)
        t.CommitEdit()
