# Language Stats

Gera um SVG com a porcentagem de uso de cada linguagem somando **todos**
os seus repositórios do GitHub — públicos e privados — parecido com o
card "Most Used Languages".

## Como configurar

1. **Crie o repositório** no GitHub (pode ser privado) e suba estes arquivos.

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

## Personalizações possíveis

- **Incluir forks**: remova o `if repo.get("fork"): continue` em
  `language_stats.py`.
- **Analisar uma organização**: defina `GH_USER=nome-da-org` (o token
  precisa ter acesso a ela).
- **Agrupar linguagens pequenas**: ajuste o parâmetro `min_percent` em
  `to_percentages()`.
- **Cores de outras linguagens**: adicione entradas no dicionário
  `LANGUAGE_COLORS`.
