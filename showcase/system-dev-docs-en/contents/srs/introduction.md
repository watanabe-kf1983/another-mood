# Purpose

This document defines the requirements on an inventory management system for a small bookstore (hereafter "the system"). Its readers are the owner of the bookstore who commissions the system, the developers who design and implement it, and those in charge of acceptance testing.

# Scope

The system covers the book stock of a single store. It maintains the stock quantities through the delivery, sales and stocktake business, and lets clerks look up the current stock at any time.

Accounting, customer management, online sales and ordering from suppliers are outside the scope of the system. The scope per unit of business work is given under [Business processes in scope](node:/srs/introduction/business_context).

# Product perspective

The system is a web application used from the PCs and tablets in the store, and it runs on its own. Payment at the counter is left to an external payment service; the system receives the content of each completed sale (books and quantities) from the payment service and reduces stock accordingly.

For external interfaces and data, this document goes no further than the requirements to be met (the [external interface requirements](node:/srs/requirements/non_functional/external_interface) among others). The definition of the interfaces and the logical data model belong to the design document.
