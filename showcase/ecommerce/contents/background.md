# EC Site Background

## Purpose

This example project demonstrates a minimal EC site data model.
The system handles user management, product catalog, and order processing.

## Design Decisions

We chose to separate `order` and `order_item` to support multiple products per order.
Product categories support hierarchical structure via `parent_id` self-reference.
