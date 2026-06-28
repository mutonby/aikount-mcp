<!-- mcp-name: io.github.mutonby/aikount-mcp -->

# Aikount MCP — Contabilidad española con IA para Claude, Cursor y ChatGPT

> **Servidor MCP de contabilidad para autónomos y pymes en España.** Lleva tu
> contabilidad a cualquier agente de IA: emite facturas, captura PDFs de gastos
> por OCR, concilia movimientos bancarios y prepara el Modelo 303 — todo desde
> Claude, Cursor, ChatGPT o cualquier cliente MCP.

[![CI](https://github.com/mutonby/aikount-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mutonby/aikount-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/aikount-mcp.svg)](https://pypi.org/project/aikount-mcp/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

Aikount es un **SaaS de contabilidad agent-first**: una alternativa a Holded
pensada para que sea una **IA quien lleve la contabilidad**. Este repositorio es
el **servidor [MCP](https://modelcontextprotocol.io) (Model Context Protocol)**
oficial que conecta tu agente de IA con tus libros a través de la API REST
pública de [Aikount](https://aikount.com). La API es el producto; la interfaz web
es el plan B para humanos.

> **¿Eres autónomo o gestoría y quieres que un agente de IA lleve tu
> contabilidad en España?** Empieza en **[aikount.com](https://aikount.com)** y
> conecta tu agente con este servidor MCP.

## ¿Qué puedes hacer? (herramientas)

| Herramienta | Qué hace |
|-------------|----------|
| `whoami` | Verifica el token y devuelve el tenant (empresa) activo |
| `list_contacts` / `create_contact` | Clientes y proveedores |
| `list_tax_types` | Tipos de IVA/IGIC/IPSI/IRPF y sus UUID para las líneas |
| `list_products` | Catálogo de productos/servicios |
| `list_invoices` / `get_invoice` | Consultar facturas de venta |
| `create_invoice` / `issue_invoice` | Crear borrador y emitir (asigna número legal) |
| `list_purchases` / `get_purchase` | Consultar gastos / facturas de compra |
| `ingest_purchase_pdf` / `get_ingest_job` | OCR de un PDF a un gasto **sin duplicados** |
| `list_treasuries` | Cuentas de banco / Stripe / PayPal con saldo |
| `list_bank_movements` | Movimientos bancarios, con filtros |
| `reconciliation_board` / `reconcile_movement` | Conciliación bancaria automática |
| `list_accounts` / `ledger` / `trial_balance` | Plan General Contable (PGC), mayor y sumas y saldos |
| `modelo_303_summary` / `modelo_303_csv` | IVA trimestral (Modelo 303) |
| `api_request` | Acceso a cualquier otro endpoint (ver OpenAPI) |

> **¿Por qué no hay `create_purchase`?** Las facturas de compra duplicadas
> corrompen los totales de gasto, el IVA soportado y la conciliación bancaria.
> Por eso los gastos solo se añaden vía `ingest_purchase_pdf`, que **deduplica
> por identidad de factura**.

## Instalación

Necesitas una **API key** de Aikount (scope `*`, con prefijo `agl_`). La generas
con el botón **«Conectar agente»** dentro de la app web de Aikount — te muestra
las líneas `export` exactas.

```bash
export AIKOUNT_TOKEN="agl_xxxxxxxxxxxxxxxxxxxxxxxx"
# opcional, por defecto producción:
# export AIKOUNT_API="https://api.aikount.com/api/v1"
```

Ejecútalo con [uv](https://docs.astral.sh/uv/) (sin instalar nada):

```bash
uvx aikount-mcp
```

O con pip/pipx:

```bash
pipx install aikount-mcp   # o: pip install aikount-mcp
aikount-mcp
```

### Claude Desktop / Claude Code

Añádelo a tu configuración MCP (`claude_desktop_config.json`, o `.mcp.json` en
Claude Code):

```json
{
  "mcpServers": {
    "aikount": {
      "command": "uvx",
      "args": ["aikount-mcp"],
      "env": { "AIKOUNT_TOKEN": "agl_xxxxxxxxxxxxxxxxxxxxxxxx" }
    }
  }
}
```

### Cursor

Ajustes → MCP → Add new server, con el mismo `command` / `args` / `env`.

## Casos de uso

- **«Emite una factura de 1.200 € a ACME por la consultoría de mayo.»** El agente
  busca el contacto, resuelve el IVA y crea el borrador; tú confirmas y lo emite.
- **«Mete este PDF de Amazon Web Services como gasto.»** OCR + alta deduplicada
  del gasto en el Plan General Contable.
- **«¿Cómo va mi IVA del segundo trimestre?»** Resumen del Modelo 303 al momento.
- **«Concilia los movimientos del banco con las facturas.»** Conciliación
  bancaria automática (auto-concilia con confianza ≥ 0,95).

## Convenciones

- **Dinero** en euros decimales (`unit_price: 1200.00`), no en céntimos. EUR
  salvo que `currency` diga otra cosa.
- **Fechas** ISO-8601 `AAAA-MM-DD`. **IDs** son UUID.
- Las líneas referencian impuestos por `tax_type_id` (UUID de `list_tax_types`),
  no por un código de texto. Omítelo para heredar el del contacto/producto.
- Los errores vuelven como `{"error": true, "status_code": ..., "detail": ...,
  "hint": ...}` para que el modelo se autocorrija (re-auth en 401, corregir el
  cuerpo en 422).
- El token tiene scope `*` — trátalo como una contraseña. El aislamiento por
  empresa (multi-tenant) es automático.

La [especificación OpenAPI](https://api.aikount.com/openapi.json) es la fuente de
la verdad para todo lo que este servidor no envuelve; accede a ella vía
`api_request`.

## Preguntas frecuentes (FAQ)

### ¿Qué es Aikount MCP?
Es un servidor MCP (Model Context Protocol) que conecta agentes de IA como
Claude, Cursor o ChatGPT con tu contabilidad en Aikount, para que la IA pueda
**emitir facturas, registrar gastos, conciliar el banco y preparar impuestos**
(Modelo 303) usando el Plan General Contable español.

### ¿Cómo conecto Claude (o Cursor/ChatGPT) con mi contabilidad?
Instala el servidor con `uvx aikount-mcp`, genera tu API key en Aikount con
«Conectar agente» y añade el bloque `mcpServers` a la configuración de tu cliente
MCP. En segundos tu agente puede leer y escribir en tus libros.

### ¿Es seguro? ¿Aikount guarda mis credenciales bancarias?
No. La conexión bancaria se hace mediante **pasarelas PSD2 reguladas** (Ponto
Connect, Salt Edge, GoCardless); Aikount **nunca** almacena credenciales del
banco. Los datos se alojan en la **UE**. El token de la API es revocable y está
aislado por empresa.

### ¿Sirve para autónomos y pymes en España?
Sí. Aikount está pensado para **autónomos y pymes españolas** y para las
**gestorías** que las supervisan, con soporte multiempresa y multidivisa, Plan
General Contable y Veri\*Factu. No sustituye a tu gestor: le entrega el trabajo
hecho para revisar y firmar.

### ¿Qué es el Modelo 303 y puede prepararlo la IA?
El **Modelo 303** es la autoliquidación trimestral del IVA en España. El agente
genera el resumen por trimestre (`modelo_303_summary`) y el detalle por
operación (`modelo_303_csv`) listos para revisar y presentar.

### ¿Es una alternativa a Holded?
Sí. Donde Holded es una suite por módulos, Aikount es un **agente de IA centrado
en hacerte la contabilidad**, con precio por tramo de facturación. Comparativa:
[aikount.com/alternativas-a-holded](https://aikount.com/alternativas-a-holded).

## Sobre Aikount

Aikount — **contabilidad española agent-first** para autónomos, pymes y
gestorías. Recursos:

- 🌐 Web: **[aikount.com](https://aikount.com)**
- 🤖 Contabilidad con IA: [aikount.com/contabilidad-con-ia](https://aikount.com/contabilidad-con-ia)
- 🏦 Conciliación bancaria automática: [aikount.com/conciliacion-bancaria-automatica](https://aikount.com/conciliacion-bancaria-automatica)
- 🧮 Calculadora de IVA trimestral (Modelo 303): [aikount.com/calculadora-iva-trimestral](https://aikount.com/calculadora-iva-trimestral)
- 🆚 Alternativa a Holded: [aikount.com/alternativas-a-holded](https://aikount.com/alternativas-a-holded)
- 📚 Documentación de la API: [api.aikount.com/docs](https://api.aikount.com/docs)
- 🧩 Contexto para agentes: [aikount.com/llms.txt](https://aikount.com/llms.txt)

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q          # 23 tests, sin red (httpx MockTransport)
```

Los tests fijan cada herramienta a la ruta **real** de la API verificada contra
la especificación OpenAPI en vivo, para que las rutas no se rompan en silencio.

`server.json` es el manifiesto de este paquete para el
[registro oficial de MCP](https://registry.modelcontextprotocol.io).

## Licencia

MIT — ver [LICENSE](LICENSE).
