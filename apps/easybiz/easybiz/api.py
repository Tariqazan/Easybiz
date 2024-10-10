import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)  # Allow guest if you want to expose it publicly, otherwise remove allow_guest
def get_companies():
    companies = frappe.get_all('Company', fields=['name'])
    return companies
