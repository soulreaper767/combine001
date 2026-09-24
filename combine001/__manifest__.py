{
    'name': 'Combine001',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Combine Spinning — Sales, Quantity Control, Tax, Commission & Accounting enhancements',
    'description': """
Combine001 — Odoo ERP Enhancements for Combine Spinning
=========================================================
Implements the Business Requirements Document "Odoo ERP Enhancements v1.0"
(Sibyl Technologies, 2026-09-16):

* Sales Order price-change approval workflow with audit trail
* Quotation -> Sales Order quantity control, plus item-wise and
  customer-wise quantity limits
* Cumulative delivery and invoice quantity validation against the Sales
  Order
* Additional charges (freight, transportation, handling, service) on the
  Sales Order
* Commission Agent assignment, automatic commission calculation on
  invoice posting, and commission reporting
* Separate Tax Ledger view and a controlled manual Tax Ledger Adjustment
  approval flow with full audit trail
* Role-based security groups (Tax Officer, Auditor) aligned to the BRD's
  RACI / access matrix, plus one demo user per BRD role (Section 3.1)
  already assigned to the correct groups
* On install AND on every upgrade: replaces the company's Chart of
  Accounts and opening trial balance with the client's actual data
  (currency PKR), imports its Customers and Vendors as Contacts, and
  creates one bank/cash journal per real bank account (see
  models/res_company.py / README for what this does and does not touch)
* Relabels "Quotation" to "Sales Contract" across the core Sales app
  (menus, buttons, filters, PDF report/print) to match the textile-trade
  terminology Combine Spinning actually uses — cosmetic only, the
  underlying sale.order model/workflow is unchanged
* Imports the real Finished Goods / Raw Material product catalog (284
  products, 18 categories) mapped onto the client's own Chart of
  Accounts; configures GST 18%/22% Sale + Purchase taxes (18% default);
  and automatically records "GST Saved" (Dr Current Asset / Cr Equity,
  entirely outside the P&L) whenever an invoice or bill posts with no
  GST charged, computed from the rate on each product's master — see
  models/res_company.py and models/account_move.py / README
* Implements the "BRD for sales.docx" Contract -> Sales Order -> Delivery
  Out -> Delivery Challan -> Gate Pass -> Sales Invoice workflow:
  Contract price is locked the moment the order is confirmed and can
  only change through a controlled Contract Amendment (draft -> submit
  -> Sales Manager approval -> apply, full chatter audit trail, always
  updates the existing line so reapplying never duplicates it); a new
  no-stock-impact Delivery Out document sits between the Sales Order and
  delivery; the existing Delivery Note/stock.picking functionality is
  reused as-is and relabeled "Delivery Challan" (the only document that
  actually deducts stock, on validation, exactly as before); a new
  no-stock-impact Gate Pass is raised from a validated Delivery Challan;
  every document carries the Contract/registration-status reference back
  to its origin
* Customer/Vendor "Tax Info" tab with separate Registered/Unregistered
  (or Filer/Non-Filer) status per tax regime - GST, Income Tax, PRA -
  that flows automatically onto every document above; PRA status is only
  shown on a document when a PRA-applicable product (flagged in that
  product's own Sales tab) is on one of its lines
* Commission Report payment tracking: Paid/Unpaid status, payment
  reference/date, Outstanding/Paid commission columns, and a bulk "Mark
  as Paid" action

Several points are explicitly left open in the BRD for client sign-off
(Section 12, "Open Items for Functional Design"). This module ships a
documented default for each so the app is usable end-to-end; see the
README for the assumptions made and how to change them:

1. Quantity hierarchy precedence -> all applicable limits enforced
   independently (most restrictive wins).
2. Price-override approval -> flat rule, any change from the quoted
   price routes to a Sales Manager.
3. Invoicing policy -> order-based (invoice qty validated against the
   Sales Order quantity).
4. Commission base -> configurable per Commission Agent / Sales Order,
   defaults to Sales Value.
5. Customer accounting dimension -> native partner_id on journal items
   (Odoo's built-in Partner Ledger), no separate GL account per customer.
6. Tax Ledger adjustment approval -> single level (Finance Manager).
""",
    'author': 'Sibyl Technologies',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'sale_management', 'sale_stock', 'account'],
    'data': [
        'security/combine001_security.xml',
        'security/ir.model.access.csv',
        'data/combine001_charge_data.xml',
        'data/ir_sequence_data.xml',
        'data/combine001_users_data.xml',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/customer_item_limit_views.xml',
        'views/charge_type_views.xml',
        'views/commission_agent_views.xml',
        'views/commission_line_views.xml',
        'wizard/add_charge_wizard_views.xml',
        'wizard/commission_payment_wizard_views.xml',
        'views/sale_amendment_views.xml',
        'views/delivery_out_views.xml',
        'views/gate_pass_views.xml',
        'views/sale_order_views.xml',
        'views/sale_quotation_to_contract_views.xml',
        'views/stock_picking_delivery_challan_views.xml',
        'views/tax_adjustment_views.xml',
        'views/tax_ledger_views.xml',
        'views/gst_saving_views.xml',
        'views/audit_views.xml',
        'views/combine001_menus.xml',
        'data/combine001_import_run.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
