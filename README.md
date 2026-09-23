# Engenharia-de-dados---Ovitrampas
# ETL Ovitrampas – Recife 2026

Pipeline ETL + notebook didático para **tratar e analisar os dados de monitoramento de ovitrampas (armadilhas de dengue) do Recife em 2026**, carregando o resultado em **SQLite** e, opcionalmente, no **MongoDB Atlas**.

## 1. Fonte de dados

- `dados/entrada/ovitrampas_2026.xlsx` — arquivo original (aba `CICLO 1`);
- `dados/entrada/ovitrampas_2026.csv` — versão convertida do xlsx (mesmo conteúdo).

O dataset conta com **31.455 registros × 17 colunas** cobrindo **12 ciclos** de coleta e **8 distritos sanitários** (DS). Cada linha representa o monitoramento de uma ovitrampa em um ciclo, com datas de coleta → apoio → laboratório → leitura → digitação envio ao DS, quantidade de armadilhas (`qt`), contagem de ovos (`n_ovos`), agente responsável, técnico de laboratório e observações.

## 2. Estrutura do projeto

```
.
├── dados/entrada/           # dados brutos (xlsx e csv)
├── banco/ovitrampas.db      # SQLite gerado pelo pipeline (não versionado)
├── notebook/
│   └── tratamento_dados_ovitrampas.ipynb   # passo a passo didático da limpeza e modelagem
├── src/
│   ├── config.py            # caminhos e constantes (DS, observações, colunas)
│   ├── extract.py           # leitura do arquivo de origem (xlsx/csv)
│   ├── transform.py         # limpeza, tratamento e organização em tabelas
│   ├── database.py          # schema (DDL) do SQLite
│   ├── load.py              # carga das tabelas no SQLite
│   ├── main.py              # executa o pipeline completo
│   └── carregar_mongodb.py  # carga opcional no MongoDB Atlas
├── .env                     # MONGODB_URI (não versionado)
├── requirements.txt         # dependências do pipeline
└── requirements-dev.txt     # dependências do notebook
```

## 3. Como executar

### 3.1 SQLite (pipeline completo)

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python src/main.py
```

O banco é recriado em `banco/ovitrampas.db` sem perda de registros (31.455 → 31.455) e o terminal mostra o **relatório da limpeza** e as contagens por tabela.

### 3.2 Notebook didático

```bash
pip install -r requirements-dev.txt
jupyter notebook notebook/tratamento_dados_ovitrampas.ipynb
```

Execute com **Kernel → Restart & Run All**. As células reproduzem todo o tratamento passo a passo (textos, datas, números, agentes, dimensional, SQLite e sanity check final).

### 3.3 MongoDB Atlas (opcional)

1. Crie um cluster gratuito no Atlas e um usuário com acesso.
2. Copie a connection string em `.env` (na raiz):

   ```
   MONGODB_URI=mongodb+srv://usuario:senha@cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

3. Carga:

   ```bash
   python src/carregar_mongodb.py
   ```

   Recria a coleção `monitoramento` do banco `ovitrampas` com os 31.455 documentos (datas como `datetime`, numéricos inteiros). Execute novamente sempre que quiser reenviar o dado já limpo.

## 4. Etapas de tratamento e limpeza

| Etapa | Ação |
|---|---|
| **Cabeçalhos** | Nomes padronizados (`ANO → ano`, `CICLOS → ciclo`, `NM_TEC_LAB → nm_tecnico_lab`, etc.). |
| **Texto** | `strip`, colapso de espaços duplicados e células vazias → `NULL`. |
| **Distrito sanitário** | Numeração romana (`I…VIII`) → inteiro `1…8`. |
| **Datas** | 6 colunas de data convertidas para `datetime`; valores em branco/inválidos → `NULL`. |
| **Números** | `qt` e `n_ovos` para numérico; `ano` e `ciclo` para inteiro. |
| **Agente/matrícula** | Separação de `AGENTE / MATRICULA`: extrai matrículas "coladas" ao nome (ex.: `ANGÉLICA BRITO79.718-0`), trata `S/M` e unifica grafias do mesmo agente com/sem acento (ex.: `JOSÉ ROBERTO`/`JOSE ROBERTO`) mantendo a grafia mais frequente. |
| **Áreas sem agente** | Placeholders `DESCOBERTA`/`ÁREA DESCOBERTA` → `NULL` (não são pessoas). |

### Impacto medido (relatório exibido ao rodar o pipeline)

| Ajuste | Quantidade |
|---|---|
| Placeholders de área descoberta → nulo | 751 |
| Matrículas "coladas" ao nome extraídas | 18 |
| Registros sem matrícula (mantidos) | 538 |
| Datas em branco (células de data) | 22.734 |
| `n_ovos > 1000` (apenas sinalizado) | 507 |
| Grafias de agentes unificadas | 16 |
| Agentes após unificação | 678 |

## 5. Modelo dimensional (SQLite)

```
dim distrito_sanitario   (id_ds        : 8)
dim bairro               (id_bairro    : 86)      bairro → distrito
dim agente               (id_agente    : 678)
dim ovitrampa            (id_ovt       : 2.871)   ovitrampa → bairro
dim tecnico_laboratorio  (id_tecnico   : 11)
dim observacao           (codigo, descricao: 6)   F/E/R/D/REC-2025/REC-2026

fato monitoramento_ovitrampa (id_registro : 31.455)
  ano, ciclo, id_ovt, id_agente, id_tecnico, codigo_obs,
  bairro_area, qt, dt_coleta, dt_entrega_apoio, dt_entrega_lab,
  dt_leitura, dt_digitacao, dt_envio_ds, n_ovos
```

`(id_ovt, ciclo)` é único na fato; todas as chaves estrangeiras são checadas (`PRAGMA foreign_key_check` retorna vazio).

## 6. Qualidade dos dados — pontos conhecidos (não alterados)

O dado bruto tem padrões esperados de um registro operacional que **não são "erros" a corrigir**, mas devem ser conhecidos:

- **993 registros** têm o bloco de monitoramento inteiro em branco (datas, técnico e digitação ausentes) — armadilha prevista no ciclo sem visita registrada.
- **`n_ovos` até 4.420** (~507 valores acima de 1.000) — faixa geralmente acima do esperado para leitura de ovitrampa; sinalizado, não removido.
- **Datas fora de ordem** (ex.: entrega na leitura, leitura depois da digitação) — atrasos de fluxo real; mantidos.
- **538 registros sem matrícula** do agente (479 sem barra e sem matrícula + 59 com `S/M`) — mantidos com `id_agente` válido.
- `bairro → DS` é consistente (nenhum bairro em dois DS) e `(id_ovt, ciclo)` não tem duplicatas.

## 7. Tecnologias

Python 3.14, pandas 3.0.5, openpyxl, SQLite (stdlib), pymongo, Jupyter.
