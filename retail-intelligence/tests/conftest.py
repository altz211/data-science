import pandas as pd
import pytest

from retail import warehouse
from retail.data import COLUMNS


def line(invoice, product, quantity, when, price, customer, country="United Kingdom", description="Thing"):
    return [invoice, product, description, quantity, pd.Timestamp(when), price, customer, country]


@pytest.fixture
def rows():
    """A tiny shop: three customers over three months, plus the awkward cases."""
    data = [
        line("1", "10001", 2, "2011-01-03 10:00", 5.0, "A"),      # A's first order
        line("1", "10002", 1, "2011-01-03 10:00", 10.0, "A"),
        line("2", "10001", 1, "2011-01-04 11:00", 5.0, "B"),      # B's first order
        line("3", "10001", 4, "2011-02-07 12:00", 5.0, "A"),      # A returns in Feb
        line("4", "10002", 1, "2011-02-08 12:00", 10.0, None),    # guest order
        line("5", "10003", 3, "2011-03-01 09:00", 2.0, "C", "France"),
        line("C6", "10001", -1, "2011-02-09 09:00", 5.0, "A"),    # a return
        line("C7", "10002", -2000, "2011-02-10 09:00", 1.0, "B"), # a large credit; cause unknown
        line("8", "POST", 1, "2011-02-08 12:00", 18.0, "A"),      # postage, not merchandise
        line("9", "10003", 5, "2011-03-02 09:00", 0.0, "C", "France"),  # free sample
    ]
    frame = pd.DataFrame(data, columns=COLUMNS)
    frame["customer_id"] = frame.customer_id.astype("string")
    return frame


@pytest.fixture
def db(rows):
    connection = warehouse.build(rows, ":memory:")
    yield connection
    connection.close()
