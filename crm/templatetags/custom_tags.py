from django import template

register = template.Library()

@register.simple_tag
def belt_badge(belt_rank, stripes=0):
    belt_class = belt_rank.lower().replace(" ", "-")

    html = f'<span class="badge {belt_class}-belt">{belt_rank.title()} '

    for _ in range(stripes):
        html += '<i class="fas fa-star belt-stripe"></i>'

    html += '</span>'

    return html
