{#
    P&L of a parallel rate shock, approximated with DV01.
    DV01 is the loss for a +1 bp rise, so a +N bp shock loses about N x DV01.
#}
{% macro rate_shock_pnl(dv01_expression, shock_bp) %}
    (-1 * {{ shock_bp }} * {{ dv01_expression }})
{% endmacro %}
