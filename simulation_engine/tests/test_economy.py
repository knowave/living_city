import unittest
import uuid

from simulation_engine.economy import (
    Account,
    AccountOwnerType,
    AccountType,
    LedgerEntry,
    Transaction,
    TransactionType,
)

OT = AccountOwnerType


def uid() -> uuid.UUID:
    return uuid.uuid4()


class AccountTest(unittest.TestCase):
    def test_defaults(self):
        a = Account(id=uid(), owner_type=OT.CITIZEN, citizen_id=uid())
        self.assertEqual(
            (a.account_type, a.currency, a.balance, a.is_active),
            (AccountType.CASH, "KRW", 0, True),
        )

    def test_valid_owners(self):
        Account(id=uid(), owner_type=OT.HOUSEHOLD, household_id=uid())
        Account(id=uid(), owner_type=OT.COMPANY, company_id=uid())
        Account(id=uid(), owner_type=OT.GOVERNMENT)
        Account(id=uid(), owner_type=OT.SYSTEM, account_type=AccountType.ISSUANCE, balance=-5)

    def test_owner_violations(self):
        bad = [
            dict(owner_type=OT.CITIZEN),
            dict(owner_type=OT.CITIZEN, citizen_id=uid(), company_id=uid()),
            dict(owner_type=OT.HOUSEHOLD, citizen_id=uid()),
            dict(owner_type=OT.COMPANY, company_id=uid(), household_id=uid()),
            dict(owner_type=OT.GOVERNMENT, citizen_id=uid()),
            dict(owner_type=OT.SYSTEM, company_id=uid()),
        ]
        for kw in bad:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                Account(id=uid(), **kw)

    def test_negative_balance(self):
        with self.assertRaises(ValueError):
            Account(id=uid(), owner_type=OT.GOVERNMENT, balance=-1)
        with self.assertRaises(ValueError):  # SYSTEM이어도 ISSUANCE가 아니면 불가
            Account(id=uid(), owner_type=OT.SYSTEM, balance=-1)
        with self.assertRaises(ValueError):  # ISSUANCE여도 SYSTEM이 아니면 불가
            Account(id=uid(), owner_type=OT.GOVERNMENT, account_type=AccountType.ISSUANCE, balance=-1)

    def test_slots(self):
        a = Account(id=uid(), owner_type=OT.GOVERNMENT)
        self.assertFalse(hasattr(a, "__dict__"))


class TransactionTest(unittest.TestCase):
    def test_defaults_and_metadata_isolated(self):
        t1 = Transaction(id=uid(), transaction_type=TransactionType.SALARY, tick=1, idempotency_key="a")
        t2 = Transaction(id=uid(), transaction_type=TransactionType.SALARY, tick=1, idempotency_key="b")
        self.assertIsNone(t1.description)
        self.assertIsNone(t1.reverses_transaction_id)
        self.assertEqual(t1.metadata, {})
        t1.metadata["x"] = 1
        self.assertEqual(t2.metadata, {})
        self.assertFalse(hasattr(t1, "__dict__"))


class LedgerEntryTest(unittest.TestCase):
    def make(self, **kw):
        return LedgerEntry(id=uid(), transaction_id=uid(), account_id=uid(), **{"entry_no": 1, "amount": 10, **kw})

    def test_valid(self):
        self.assertEqual(self.make(amount=-10).amount, -10)
        self.assertFalse(hasattr(self.make(), "__dict__"))

    def test_violations(self):
        with self.assertRaises(ValueError):
            self.make(amount=0)
        with self.assertRaises(ValueError):
            self.make(entry_no=0)


class EnumValueTest(unittest.TestCase):
    def test_values_match_backend(self):
        self.assertEqual({e.value for e in OT}, {"CITIZEN", "HOUSEHOLD", "COMPANY", "GOVERNMENT", "SYSTEM"})
        self.assertEqual({e.value for e in AccountType}, {"CASH", "SAVINGS", "TREASURY", "ISSUANCE"})
        self.assertEqual(
            {e.value for e in TransactionType},
            {
                "OPENING_BALANCE", "SALARY", "PURCHASE", "INCOME_TAX", "RENT", "WELFARE",
                "ACCOUNT_TRANSFER", "CAPITAL_INVESTMENT", "ADJUSTMENT", "REVERSAL",
            },
        )
        for e in (*OT, *AccountType, *TransactionType):
            self.assertEqual(e, e.name)


if __name__ == "__main__":
    unittest.main()
