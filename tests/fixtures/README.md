# Test fixtures

Real result pages from cnmv.es, captured on 2026-11-06, so the parser tests run offline.

To keep them small they were trimmed: only `section#maincontent` is kept (no
site header, menus, scripts or ASP.NET viewstate), and the result list keeps
2-3 of the 10 entries per page. The markup of each entry is untouched.

| File | Source URL |
|---|---|
| `oir_dias3_page1.html` | `/portal/Otra-Informacion-Relevante/Resultado-OIR?dias=3` |
| `oir_dias3_page8_last.html` | `/portal/otra-informacion-relevante/resultado-oir.aspx?dias=3&page=7` |
| `ip_dias7_page1.html` | `/portal/Informacion-Privilegiada/Resultado-IP?dias=7` |

Note: `page` in the URL is zero-based (`page=7` is "Página 8 de 8").
