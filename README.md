# Combine001

Odoo 19 custom app skeleton.

## Layout

- `combine001/` — the Odoo module (installable, `application: True`)

## Install

Addon lives under `~/odoo/custom/` (symlinked as `combine001` -> `combine001_odoo/combine001`) on the WSL Odoo instance, addons path already includes `~/odoo/custom`. Install/update via:

```
odoo-bin -c <conf> -d <db> -i combine001 --stop-after-init
```
