"""Controlled mutation demonstration; not a real banking implementation."""


def withdraw(balance, amount):
    if amount <= balance:
        return balance - amount
    raise ValueError("Insufficient funds")
