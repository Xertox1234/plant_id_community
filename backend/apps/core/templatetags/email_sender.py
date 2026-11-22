"""``{% email_sender_footer %}`` and ``{% email_sender_footer_text %}``: the
sender's name and postal address in an email footer (todo 703).

``emails/base.html`` prints the HTML one outside its ``footer`` block, so a
template that overrides the block keeps it. Every ``.txt`` email ends with
the text one, since the text parts have no shared base. The values come from
``apps.core.context_processors.email_sender``, read at render time.
"""

from apps.core.context_processors import email_sender
from django import template

register = template.Library()


@register.inclusion_tag("emails/_sender_footer.html")
def email_sender_footer() -> dict[str, str]:
    return email_sender()


@register.inclusion_tag("emails/_sender_footer.txt")
def email_sender_footer_text() -> dict[str, str]:
    return email_sender()
