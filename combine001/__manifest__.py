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
        'views/customer_item_limit_views.xml',
        'views/charge_type_views.xml',
        'views/commission_agent_views.xml',
        'views/commission_line_views.xml',
        'wizard/add_charge_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/tax_adjustment_views.xml',
        'views/tax_ledger_views.xml',
        'views/audit_views.xml',
        'views/combine001_menus.xml',
        'data/combine001_import_run.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
