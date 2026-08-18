#!/usr/bin/env python3
"""Split Italian and Portuguese out of the English interior-design draft."""

from __future__ import annotations

import base64
import json
import os

import paramiko


CAMPAIGNS = {
    "Italian": {
        "code": "it",
        "list": "interior design italian",
        "subject": "Una breve idea per il suo studio",
        "body": """<p>Salve,</p>
<p>Stavo cercando su Google Maps interior designer, architetti d'interni, studi di architettura e imprese di costruzione nella zona e mi sono imbattuto nella sua attività, quindi ho pensato di contattarla.</p>
<p>Ho dato un'occhiata al suo sito web e ho notato alcune aree che potrebbero essere migliorate, in particolare <strong>l'esperienza da dispositivi mobili, le prestazioni e alcuni contenuti</strong>. Sono aspetti che potremmo potenzialmente sistemare in meno di due ore.</p>
<p>Siamo una società di sviluppo software e questa è solo una brevissima introduzione a due soluzioni che offriamo a professionisti e aziende che operano nell'interior design, nell'architettura, nella ristrutturazione e nell'edilizia:</p>
<p><strong>1. Siti web per interior design</strong> – Rebranding, riprogettazione o miglioramento del sito web esistente per offrire al suo studio o alla sua azienda una presenza online più moderna, professionale e visivamente accattivante. L'IA sta cambiando le regole del gioco nel web design e alcuni dei nuovi design e delle nuove possibilità sono davvero sorprendenti, soprattutto per settori altamente visivi come l'interior design e l'architettura.</p>
<p><strong>2. Software personalizzato per studi</strong> – Software personalizzato per gestire richieste dei clienti, progetti, follow-up, proposte, fatture e altri processi quotidiani in un unico posto, costruito attorno al modo in cui opera realmente la sua attività.</p>
<p>Può dare una rapida occhiata a entrambe le soluzioni qui:<br><a href="https://consthruads.com/interior-designers/?lang=it" target="_blank" rel="noopener noreferrer">https://consthruads.com/interior-designers/?lang=it</a></p>
<p>Se ritiene che possa essere utile per il suo studio o la sua azienda, sarei lieto di fare una breve chiacchierata.</p>
<p>Cordiali saluti,<br>Edward</p>
<p><a href="https://consthruads.com/?lang=en" target="_blank" rel="noopener noreferrer">https://consthruads.com/?lang=en</a></p>""",
    },
    "Portuguese": {
        "code": "port",
        "list": "interior design portuguese",
        "subject": "Uma breve ideia para o seu estúdio",
        "body": """<p>Olá,</p>
<p>Estava a procurar no Google Maps designers de interiores, arquitetos de interiores, estúdios de arquitetura e empresas de construção na zona e encontrei a sua empresa, por isso pensei em entrar em contacto.</p>
<p>Dei uma vista de olhos ao seu website e reparei em algumas áreas que poderiam ser melhoradas, em particular <strong>a experiência em dispositivos móveis, o desempenho e alguns conteúdos</strong>. São aspetos que poderíamos potencialmente corrigir em menos de duas horas.</p>
<p>Somos uma empresa de desenvolvimento de software e esta é apenas uma breve apresentação de duas soluções que oferecemos a profissionais e empresas que trabalham em design de interiores, arquitetura, renovação e construção:</p>
<p><strong>1. Websites de design de interiores</strong> – Rebranding, reformulação ou melhoria do seu website atual para proporcionar ao seu estúdio ou empresa uma presença online mais moderna, profissional e visualmente impressionante. A IA está a mudar as regras do web design e alguns dos novos designs e possibilidades são absolutamente surpreendentes, especialmente para setores altamente visuais como o design de interiores e a arquitetura.</p>
<p><strong>2. Software personalizado para estúdios</strong> – Software personalizado para gerir pedidos de clientes, projetos, acompanhamentos, propostas, faturas e outros processos diários num único lugar, desenvolvido em torno da forma como a sua empresa realmente funciona.</p>
<p>Pode ver rapidamente ambas as soluções aqui:<br><a href="https://consthruads.com/interior-designers/?lang=port" target="_blank" rel="noopener noreferrer">https://consthruads.com/interior-designers/?lang=port</a></p>
<p>Se lhe parecer relevante para o seu estúdio ou empresa, terei todo o gosto em ter uma breve conversa.</p>
<p>Com os melhores cumprimentos,<br>Edward</p>
<p><a href="https://consthruads.com/?lang=en" target="_blank" rel="noopener noreferrer">https://consthruads.com/?lang=en</a></p>""",
    },
}


def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


FROM_EMAIL = os.environ.get("LISTMONK_FROM_EMAIL", "").strip()
if not FROM_EMAIL:
    raise RuntimeError("LISTMONK_FROM_EMAIL must contain the approved sender identity")


defs = ",".join(
    f"({q(language)},{q(data['code'])},{q('Interior Design Solutions - ' + language)},{q(data['subject'])},{q(data['body'])},{q(data['list'])})"
    for language, data in CAMPAIGNS.items()
)

sql = f"""\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(82496681);
CREATE TEMP TABLE defs(language text,code text,campaign_name text,subject text,body text,list_name text);
INSERT INTO defs VALUES {defs};
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM defs d LEFT JOIN lists l ON l.name=d.list_name WHERE l.id IS NULL) THEN RAISE EXCEPTION 'Missing language list'; END IF;
 IF EXISTS (SELECT 1 FROM campaigns c JOIN defs d ON d.campaign_name=c.name WHERE c.status<>'draft' OR c.sent<>0) THEN RAISE EXCEPTION 'Campaign name collision'; END IF;
END $$;
INSERT INTO campaigns(uuid,name,subject,from_email,body,content_type,status,type,messenger,template_id)
SELECT gen_random_uuid(),d.campaign_name,d.subject,{q(FROM_EMAIL)},d.body,'html','draft','regular','email',1
FROM defs d WHERE NOT EXISTS(SELECT 1 FROM campaigns c WHERE c.name=d.campaign_name);
UPDATE campaigns c SET subject=d.subject,body=d.body,from_email={q(FROM_EMAIL)},content_type='html',messenger='email',template_id=1,updated_at=now()
FROM defs d WHERE c.name=d.campaign_name AND c.status='draft' AND c.sent=0;
DELETE FROM campaign_lists cl USING campaigns c,defs d WHERE cl.campaign_id=c.id AND c.name=d.campaign_name;
INSERT INTO campaign_lists(campaign_id,list_id,list_name)
SELECT c.id,l.id,l.name FROM campaigns c JOIN defs d ON d.campaign_name=c.name JOIN lists l ON l.name=d.list_name;
DELETE FROM campaign_lists cl USING campaigns c,lists l
WHERE cl.campaign_id=c.id AND cl.list_id=l.id AND c.name='Interior Design Solutions - English' AND l.name IN ('interior design italian','interior design portuguese');
WITH stats AS (
 SELECT c.id,COUNT(DISTINCT s.id)::integer n,COALESCE(MAX(s.id),0)::integer max_id
 FROM campaigns c JOIN campaign_lists cl ON cl.campaign_id=c.id JOIN subscriber_lists sl ON sl.list_id=cl.list_id AND sl.status='confirmed'
 JOIN subscribers s ON s.id=sl.subscriber_id AND s.status='enabled'
 WHERE c.name IN ('Interior Design Solutions - English','Interior Design Solutions - Italian','Interior Design Solutions - Portuguese')
 AND NOT EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id)
 GROUP BY c.id
) UPDATE campaigns c SET to_send=stats.n,max_subscriber_id=stats.max_id,last_subscriber_id=0 FROM stats WHERE c.id=stats.id;
SELECT json_build_object(
 'campaigns',(SELECT json_agg(json_build_object('id',c.id,'name',c.name,'targets',c.to_send,'status',c.status,'sent',c.sent,'lists',(SELECT json_agg(cl.list_name ORDER BY cl.list_name) FROM campaign_lists cl WHERE cl.campaign_id=c.id)) ORDER BY c.id) FROM campaigns c WHERE c.name IN ('Interior Design Solutions - English','Interior Design Solutions - Italian','Interior Design Solutions - Portuguese')),
 'overlap',(SELECT COUNT(*) FROM (SELECT sl.subscriber_id FROM campaigns c JOIN campaign_lists cl ON cl.campaign_id=c.id JOIN subscriber_lists sl ON sl.list_id=cl.list_id AND sl.status='confirmed' WHERE c.name IN ('Interior Design Solutions - English','Interior Design Solutions - Italian','Interior Design Solutions - Portuguese') GROUP BY sl.subscriber_id HAVING COUNT(DISTINCT c.id)>1) x),
 'unsafe',(SELECT COUNT(*) FROM campaigns c JOIN campaign_lists cl ON cl.campaign_id=c.id JOIN subscriber_lists sl ON sl.list_id=cl.list_id JOIN subscribers s ON s.id=sl.subscriber_id WHERE c.name IN ('Interior Design Solutions - English','Interior Design Solutions - Italian','Interior Design Solutions - Portuguese') AND sl.status='confirmed' AND (s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id))),
 'bad_links',(SELECT COUNT(*) FROM campaigns c JOIN defs d ON d.campaign_name=c.name WHERE position('interior-designers/?lang='||d.code in c.body)=0),
 'not_draft',(SELECT COUNT(*) FROM campaigns c WHERE c.name IN ('Interior Design Solutions - English','Interior Design Solutions - Italian','Interior Design Solutions - Portuguese') AND (c.status<>'draft' OR c.sent<>0))
);
COMMIT;"""


def run(client: paramiko.SSHClient, command: str, timeout: int = 1200) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode("utf-8", "replace")
    error = stderr.read().decode("utf-8", "replace")
    if error.strip():
        raise RuntimeError(error)
    return output


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(os.environ["LISTMONK_VPS_HOST"], username="root", password=os.environ["LISTMONK_VPS_PASSWORD"], timeout=20)
    try:
        stamp = run(client, "date -u +%Y%m%d_%H%M%S").strip()
        backup = f"/root/listmonk-backups/pre_interior_extended_languages_{stamp}.dump"
        run(client, f'''mkdir -p /root/listmonk-backups && docker exec listmonk-production-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > {backup} && test -s {backup}''')
        encoded = base64.b64encode(sql.encode("utf-8")).decode("ascii")
        output = run(client, f'''docker exec listmonk-production-postgres-1 sh -lc 'echo {encoded} | base64 -d | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' ''')
        result = json.loads([line for line in output.splitlines() if line.startswith("{")][-1])
        result["backup"] = backup
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
