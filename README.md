# github-lang-stats

Gera um SVG com a porcentagem de uso de cada linguagem somando **todos**
os seus repositórios do GitHub — públicos e privados — parecido com o
card "Most Used Languages".

![Minhas linguagens](./language-stats.svg)

> A imagem acima é o próprio `language-stats.svg` gerado pelo workflow.
> Como ele fica salvo neste repositório e o README o referencia com
> caminho relativo (`./language-stats.svg`), o gráfico aparece
> automaticamente pra qualquer pessoa que abrir esta página no GitHub —
> não precisa colocar em outro repositório nem em outro README.
> Na primeira execução do workflow o arquivo ainda não existe, então a
> imagem só aparece depois do primeiro run (manual ou automático).

## Como configurar

1. **Crie o repositório** no GitHub chamado, por exemplo, `github-lang-stats`
   (pode ser privado ou público — funciona nos dois casos) e suba estes
   arquivos nele.

2. **Crie um Personal Access Token (PAT)**:
   - Vá em GitHub → Settings → Developer settings → Personal access tokens
     → Fine-grained tokens (ou classic).
   - Dê o escopo `repo` (para enxergar repositórios privados) e
     `read:user`.
   - Copie o token gerado.

3. **Adicione o token como Secret** no repositório onde está este projeto:
   - Settings → Secrets and variables → Actions → New repository secret
   - Nome: `GH_PAT`
   - Valor: o token copiado no passo 2.

   > O `GITHUB_TOKEN` automático do Actions **não funciona** aqui, pois só
   > enxerga o próprio repositório onde a Action roda — por isso é
   > necessário um PAT pessoal.

4. **Pronto.** O workflow em
   `.github/workflows/update-language-stats.yml` roda todo dia às 06h
   (UTC) e sempre que você disparar manualmente em Actions → Run workflow.
   Ele gera/atualiza o arquivo `language-stats.svg` e faz commit
   automaticamente.

5. **Exiba o SVG** onde quiser, por exemplo no seu README de perfil:

   ```markdown
   ![Minhas linguagens](https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/language-stats.svg)
   ```

## Rodar localmente (teste)

```bash
pip install -r requirements.txt
export GH_TOKEN=ghp_xxx
python language_stats.py
```

Isso gera `language-stats.svg` na pasta atual e imprime o percentual de
cada linguagem no terminal.

## Como o cálculo funciona

Para cada repositório seu (públicos **e privados**), o script lê a árvore de
arquivos da branch padrão e soma o tamanho em bytes dos arquivos de código,
classificando pela extensão. Repositórios novos entram sozinhos na próxima
execução diária.

A tabela de extensões e cores vem do [GitHub Linguist](https://github.com/github-linguist/linguist)
(a mesma que o GitHub usa), baixada a cada execução, então qualquer linguagem
que o GitHub reconhece (GDScript, GDShader, ...) é contada sem mexer no código.
Extensões ambíguas (`.gd` pode ser GDScript ou GAP) são resolvidas pelas
linguagens que o próprio GitHub detectou naquele repositório.

Pastas geradas ou de dependências (`build/`, `dist/`, `node_modules/`,
`venv/`, ...) são ignoradas, então artefatos commitados sem querer (por
exemplo, o `build/` do PyInstaller, que o GitHub mostra como "TeX") não
distorcem o resultado. Dados e prosa (JSON, YAML, SQL, Markdown) também não
contam, como no GitHub. Todas as linguagens encontradas aparecem no gráfico,
sem agrupar em "Other", mesmo com porcentagens muito pequenas (`0.03%`).
Forks e repositórios arquivados são ignorados.

## Personalizações possíveis

- **Incluir forks/arquivados**: ajuste a condição em `aggregate_languages()`
  em `language_stats.py`.
- **Analisar uma organização**: defina `GH_USER=nome-da-org` (o token
  precisa ter acesso a ela).
- **Ignorar mais pastas**: adicione nomes em `IGNORED_DIRS`.
- **Preferir uma linguagem numa extensão ambígua**: adicione a extensão em
  `EXTENSIONS` (linguagens novas já vêm do Linguist automaticamente).
