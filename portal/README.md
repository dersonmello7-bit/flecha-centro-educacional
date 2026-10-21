# Flecha — Área da Família

Portal privado Django, separado do sistema de gestão existente. Não inclui banco, dados de alunos, credenciais ou contas de produção.

Produção: PostgreSQL em schema privado `flecha_portal`, armazenamento S3 privado e entrega de convites por HTTPS. Configure os segredos exclusivamente no provedor. Nunca publique os modos FLECHA_LOCAL ou FLECHA_TEST.

Build a partir da raiz do repositório:
`pip install -r portal/requirements.txt && cd portal && python manage.py collectstatic --noinput`

Início: `cd portal && python start_render.py`

Health check: `/health/`. O início aplica migrações e pode enviar o primeiro convite administrativo, quando BOOTSTRAP_ADMIN_EMAIL está definido. Não carrega demonstração.

Os comandos prepare_admin e seed_demo são apenas locais. Os arquivos são liberados pela equipe após revisão; uploads não conciliam pagamentos automaticamente.

Planos gratuitos têm suspensão por inatividade e limites. Homologue banco, arquivos, recuperação e backups antes de cadastrar dados reais.
