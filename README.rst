GnuCash Autobudget
==================

**NOTE** This program is under development and doesn't work yet. Strangely
enough, the README is fairly complete, though. Sorry! I'm not sure when I
will continue development. If you want to get involved, send me a message!

**UPDATE 2017** I've started using hledger with hledger-rewrite for my
accounting and budgeting, so I won't continue working on GnuCash Autobudget.
Sorry! Feel free to take over the code.

.. contents::


Installation
------------

You need the `GnuCash Python bindings`__ installed on your computer. If
you've installed GnuCash through the package manager, you probably
already have them. If you're not sure, just try to install GnuCash
Autobudget and it will complain if it can't find the bindings.

__ http://wiki.gnucash.org/wiki/Python_Bindings

Install::

    $ pip install [--user] gnucash_autobudget
    or
    $ easy_install [--user] gnucash_autobudget
    or 
    $ git clone https://github.com/rmoehn/gnucash_autobudget.git
    $ cd gnucash_autobudget
    $ sudo python setup.py install


Usage
-----

::

    $ gnucash_autobudget in.gnucash out.gnucash

This will create a file ``out.gnucash`` which is the same as
``in.gnucash`` except that the transactions for which it applies will
have budgeting entries added to them.


Idea
----

I had been using YNAB for my personal finances, but got fed up, because it
doesn't support accounting in multiple currencies. So I switched to GnuCash,
which does support accounting in multiple currencies, but doesn't have a special
function for envelope budgeting (zero-sum budgeting, YNAB budgeting). However,
coming from YNAB, envelope budgeting is quite important to me.

Searching the web, I found several implementations of envelope budgeting in
GnuCash, but those that appeared 'clean' required some manual transaction
splitting. This is tedious, especially when your transactions are already
bloated with currency adjustment data.

So I take the in my opinion cleanest (I don't know much about accounting,
though) `method of envelope budgeting`__ with GnuCash and use GnuCash Autobudget
to automatically add budgeting entries to transactions.

__ https://www.reddit.com/r/GnuCash/comments/3z5b6m/ynab_method_of_budgeting_with_gnucash/czvmtdd


Account setup
-------------

Please read the Reddit post linked above first and create some transactions
according to that method, so that you get a feel for it.

GnuCash Autobudget expects a setup similar to the one shown there::

    Assets                      asset
        Cash                    asset
    Expenses                    expense     mandatory
        Daily                   expense
            Groceries           expense
            Beer                expense
            Transportation      expense
        Monthly                 expense
            Rent                expense
    Budget                      asset       mandatory
        Budgeted Funds          liability   mandatory
        Available to Budget     asset       mandatory 
        Daily                   asset
            Groceries           asset
            Transportation      asset
        Monthly                 asset
            Rent                asset
        
        
For GnuCash Autobudget to work, you must have the mandatory accounts and they
must have the same name as listed above. The other accounts are only for
illustration and you can structure and name them as you want. Note, though, that
GnuCash Autobudget relies on the correspondence of subaccount names under
Expenses and Budget. Namely…

GnuCash Autobudget only looks at subaccounts of Expenses that have a
corresponding subaccount in Budget. So for example, ``Expenses:Daily:Groceries``
corresponds to ``Budget:Daily:Groceries``. If there is no corresponding
subaccount for an account in Expenses, GnuCash Autobudget will ignore it. For
example, it will ignore ``Expenses:Daily:Beer``.


What does it do?
----------------

When GnuCash looks through those accounts, it looks for transactions that don't
have a budget entry. Like this::

    #                          debit  credit
    Expenses:Daily:Groceries   100
    Assets:Cash                       100

It then adds budget entries to them::

    Expenses:Daily:Groceries   100
    Assets:Cash                       100
    Budget:Budgeted Funds      100
    Budget:Daily:Groceries            100

That means you can record your transactions as usual and GnuCash Autobudget adds
the obvious information, so that your budgeting accounts will show the right
information. Of course, GnuCash Autobudget won't touch transactions that already
have a budget entry.


Split transactions
------------------

GnuCash Autobudget can also deal with split transactions. Input::

    Expenses:Daily:Food        70
    Expenses:Daily:Drink       10
    Assets:Cash                       80

Output::

    Expenses:Daily:Food        70
    Expenses:Daily:Drink       10
    Assets:Cash                       80
    Budget:Budgeted Funds      80
    Budget:Daily:Food                 70
    Budget:Daily:Drink                10

Multi-currency splits work, too. Input::

    #                                debit  credit
    Expenses:Daily:Groceries         2 €
    Currency Trading:CURRENCY:JPY    250
    Assets:Cash:Yen                         250
    Currency Trading:CURRENCY:EUR           2 €
    
Output::

    Expenses:Daily:Groceries         2 €
    Currency Trading:CURRENCY:JPY    250
    Assets:Cash:Yen                         250
    Currency Trading:CURRENCY:EUR           2 €
    Budget:Budgeted Funds            2 €
    Budget:Daily:Groceries                  2 €


Wish list poll
--------------

There are some GitHub issues labelled ``wish list``. They denote things I might
implement in the future. You can encourage me to implement a certain feature by
commenting on the issue. Of course, you can also add items to the wish list.


Copyright and License
---------------------

See ``LICENSE.txt``.
