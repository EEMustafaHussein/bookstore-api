from sqlmodel import Session

from app.orders import cancel_order, mark_paid, stale_unpaid_orders
from app.payments import stripe


def release_stale_orders(session: Session) -> None:
    """Cancels card orders that were never paid, so their pieces go back on sale."""
    for order in stale_unpaid_orders(session):
        if order.payment_provider == "stripe" and order.payment_reference:
            try:
                checkout_session = stripe.retrieve_checkout_session(order.payment_reference)
            except stripe.PaymentError:
                # Without a clear answer from Stripe the order is left alone and checked again later.
                continue
            if stripe.session_is_paid(checkout_session, order):
                mark_paid(session, order, "stripe", checkout_session.get("id", ""))
                continue
            if checkout_session.get("status") == "open":
                continue
        cancel_order(session, order)
