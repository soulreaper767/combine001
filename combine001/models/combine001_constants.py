"""Shared constants referenced by more than one model file.

Kept in one place so the account codes used to *create* the GST Saving
accounts (models/res_company.py) and the codes used to *look them up*
when posting an invoice/bill (models/account_move.py) can never drift
apart.
"""

GST_SAVING_ASSET_CODE = '3.13.01.0001'
GST_SAVING_EQUITY_CODE = '1.09.01.0001'
