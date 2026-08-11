#!/usr/bin/env python3
"""Create bounce-safe, multilingual dental audiences and draft campaigns."""
import base64
import json
import os
import re
from pathlib import Path

import paramiko


ROOT = Path("listmonk_emails/clean_emails_odontologist")
COUNTRIES = []
for folder in ROOT.iterdir():
    if folder.is_dir():
        match = re.match(r"^\d+ - (.*?) \(\d+\)$", folder.name)
        if match:
            COUNTRIES.append(match.group(1))

SPECIAL = {
    "Spanish": {"Andorra", "Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica", "Dominican Republic", "Ecuador", "El Salvador", "Honduras", "Mexico", "Panama", "Paraguay", "Peru", "Spain", "Uruguay"},
    "Portuguese": {"Brazil", "Macao", "Portugal", "Timor Leste"},
    "French": {"France", "French Guiana", "Martinique", "New Caledonia", "Saint Martin"},
    "German": {"Austria", "Germany", "Liechtenstein", "Switzerland"},
    "Italian": {"Italy", "San Marino"},
    "Dutch": {"Aruba", "Belgium", "Bonaire, Saint Eustatius and Saba", "Suriname", "The Netherlands"},
    "Greek": {"Cyprus", "Greece"},
    "Polish": {"Poland"},
    "Romanian": {"Moldova", "Romania"},
    "Czech": {"Czechia"},
    "Slovak": {"Slovakia"},
    "Hungarian": {"Hungary"},
    "Croatian": {"Croatia", "Montenegro", "Serbia", "Slovenia"},
    "Bulgarian": {"Bulgaria", "North Macedonia"},
    "Arabic": {"Bahrain", "Kuwait", "Oman", "Qatar", "Saudi Arabia", "United Arab Emirates"},
    "Russian": {"Armenia", "Azerbaijan", "Georgia", "Mongolia"},
    "Albanian": {"Albania"},
}

# subject, greeting, discovered, intro, heading, agency, web heading, web copy,
# lead heading, lead copy, link intro, goal, meeting, closing
T = {
"English": ["A quick idea for your clinic", "Dear Dental Professionals,", "I was searching on Google Maps for dental clinics in the area and came across your practice. After reviewing your online presence, I thought it would be worthwhile to introduce myself and what we do.", "I’m Eduardo Villodre, founder of ConsthruAds and MEDIF LTD, based in Cyprus. I would be delighted to meet you and explore how we could help your clinic attract more patients and strengthen its digital presence.", "Digital Growth & Patient Acquisition for Dental Clinics", "At ConsthruAds, we help dental clinics turn their online presence into a consistent source of new patient enquiries.", "Website & Online Presence", "We create a professional, conversion-focused digital presence that clearly presents your treatments, builds trust and makes it easy to contact the clinic or request an appointment.", "Patient Lead Generation", "We create targeted digital advertising campaigns designed to reach people looking for dental treatments and turn that interest into qualified patient enquiries.", "You can see our complete solution for dental clinics here:", "Our goal is simple: help your clinic get found by the right patients and convert that visibility into real enquiries and appointments.", "I would be happy to show you how the system works and discuss how it could be adapted to your clinic. Would you be available for a 20–30 minute meeting next week?", "Kind regards"],
"Spanish": ["Una idea rápida para su clínica", "Estimados profesionales de la odontología:", "Buscando clínicas dentales de la zona en Google Maps encontré su clínica. Tras revisar su presencia online, pensé que sería oportuno presentarme y explicar brevemente lo que hacemos.", "Soy Eduardo Villodre, fundador de ConsthruAds y MEDIF LTD, con sede en Chipre. Me encantaría conocerles y estudiar cómo podemos ayudar a su clínica a atraer más pacientes y reforzar su presencia digital.", "Crecimiento digital y captación de pacientes para clínicas dentales", "En ConsthruAds ayudamos a las clínicas dentales a convertir su presencia online en una fuente constante de nuevas consultas de pacientes.", "Sitio web y presencia online", "Creamos una presencia digital profesional y orientada a la conversión que presenta claramente sus tratamientos, genera confianza y facilita el contacto o la solicitud de cita.", "Captación de pacientes", "Creamos campañas de publicidad digital dirigidas a personas que buscan tratamientos dentales y convertimos ese interés en consultas cualificadas.", "Puede ver aquí nuestra solución completa para clínicas dentales:", "Nuestro objetivo es sencillo: ayudar a que los pacientes adecuados encuentren su clínica y convertir esa visibilidad en consultas y citas reales.", "Estaré encantado de mostrarle cómo funciona el sistema y cómo adaptarlo a su clínica. ¿Tendría disponibilidad para una reunión de 20–30 minutos la próxima semana?", "Un cordial saludo"],
"Portuguese": ["Uma ideia rápida para a sua clínica", "Caros profissionais de medicina dentária,", "Ao pesquisar clínicas dentárias na região no Google Maps, encontrei a sua clínica. Depois de analisar a sua presença online, achei oportuno apresentar-me e explicar brevemente o que fazemos.", "Sou Eduardo Villodre, fundador da ConsthruAds e da MEDIF LTD, sediadas no Chipre. Terei todo o gosto em conhecê-los e explorar como podemos ajudar a clínica a atrair mais pacientes e reforçar a sua presença digital.", "Crescimento digital e captação de pacientes para clínicas dentárias", "Na ConsthruAds ajudamos clínicas dentárias a transformar a presença online numa fonte consistente de novos pedidos de pacientes.", "Website e presença online", "Criamos uma presença digital profissional e orientada para conversões, que apresenta claramente os tratamentos, gera confiança e facilita o contacto ou pedido de consulta.", "Captação de pacientes", "Criamos campanhas digitais direcionadas a pessoas que procuram tratamentos dentários e transformamos esse interesse em contactos qualificados.", "Conheça aqui a nossa solução completa para clínicas dentárias:", "O nosso objetivo é simples: ajudar os pacientes certos a encontrar a sua clínica e converter essa visibilidade em pedidos e consultas reais.", "Terei todo o gosto em mostrar como funciona e como pode ser adaptado à sua clínica. Teria disponibilidade para uma reunião de 20–30 minutos na próxima semana?", "Com os melhores cumprimentos"],
"French": ["Une idée rapide pour votre clinique", "Chers professionnels dentaires,", "En recherchant des cliniques dentaires dans la région sur Google Maps, j’ai découvert votre établissement. Après avoir consulté votre présence en ligne, j’ai pensé qu’il serait utile de me présenter et d’expliquer brièvement notre activité.", "Je suis Eduardo Villodre, fondateur de ConsthruAds et de MEDIF LTD, basées à Chypre. Je serais ravi de vous rencontrer et d’étudier comment nous pourrions aider votre clinique à attirer davantage de patients et à renforcer sa présence numérique.", "Croissance numérique et acquisition de patients pour les cliniques dentaires", "Chez ConsthruAds, nous aidons les cliniques dentaires à faire de leur présence en ligne une source régulière de nouvelles demandes de patients.", "Site web et présence en ligne", "Nous créons une présence numérique professionnelle axée sur la conversion, qui présente clairement vos soins, inspire confiance et facilite la prise de contact ou de rendez-vous.", "Acquisition de patients", "Nous créons des campagnes publicitaires ciblées pour toucher les personnes qui recherchent des soins dentaires et transformer leur intérêt en demandes qualifiées.", "Découvrez ici notre solution complète pour les cliniques dentaires :", "Notre objectif est simple : aider les bons patients à trouver votre clinique et convertir cette visibilité en demandes et rendez-vous réels.", "Je serais heureux de vous montrer le fonctionnement du système et son adaptation à votre clinique. Seriez-vous disponible pour un échange de 20 à 30 minutes la semaine prochaine ?", "Bien cordialement"],
"German": ["Eine kurze Idee für Ihre Praxis", "Sehr geehrte Zahnärztinnen und Zahnärzte,", "Bei der Suche nach Zahnarztpraxen in Ihrer Region auf Google Maps bin ich auf Ihre Praxis gestoßen. Nachdem ich Ihren Online-Auftritt angesehen hatte, wollte ich mich und unsere Arbeit kurz vorstellen.", "Ich bin Eduardo Villodre, Gründer von ConsthruAds und MEDIF LTD mit Sitz in Zypern. Gerne würde ich Sie kennenlernen und besprechen, wie wir Ihrer Praxis helfen können, mehr Patienten zu gewinnen und ihre digitale Präsenz zu stärken.", "Digitales Wachstum und Patientengewinnung für Zahnarztpraxen", "ConsthruAds hilft Zahnarztpraxen dabei, ihren Online-Auftritt in eine beständige Quelle neuer Patientenanfragen zu verwandeln.", "Website und Online-Präsenz", "Wir schaffen einen professionellen, auf Anfragen ausgerichteten Online-Auftritt, der Behandlungen verständlich präsentiert, Vertrauen schafft und Kontakt oder Terminvereinbarung erleichtert.", "Patientengewinnung", "Mit gezielten digitalen Werbekampagnen erreichen wir Menschen, die nach Zahnbehandlungen suchen, und verwandeln ihr Interesse in qualifizierte Anfragen.", "Unsere Komplettlösung für Zahnarztpraxen finden Sie hier:", "Unser Ziel ist einfach: Ihre Praxis für die richtigen Patienten sichtbar zu machen und diese Sichtbarkeit in echte Anfragen und Termine umzuwandeln.", "Gerne zeige ich Ihnen das System und bespreche eine Anpassung an Ihre Praxis. Hätten Sie nächste Woche 20–30 Minuten Zeit?", "Mit freundlichen Grüßen"],
"Italian": ["Una breve idea per la sua clinica", "Gentili professionisti del settore dentale,", "Cercando cliniche dentali della zona su Google Maps ho trovato la vostra struttura. Dopo aver visto la vostra presenza online, ho pensato che valesse la pena presentarmi e spiegare brevemente cosa facciamo.", "Sono Eduardo Villodre, fondatore di ConsthruAds e MEDIF LTD, con sede a Cipro. Sarebbe un piacere conoscervi e valutare come aiutare la clinica ad attirare più pazienti e rafforzare la presenza digitale.", "Crescita digitale e acquisizione di pazienti per cliniche dentali", "In ConsthruAds aiutiamo le cliniche dentali a trasformare la presenza online in una fonte costante di nuove richieste.", "Sito web e presenza online", "Creiamo una presenza digitale professionale orientata alla conversione, che presenta chiaramente i trattamenti, crea fiducia e facilita il contatto o la prenotazione.", "Acquisizione di pazienti", "Creiamo campagne pubblicitarie digitali mirate per raggiungere chi cerca trattamenti dentali e trasformare l’interesse in richieste qualificate.", "Qui può vedere la nostra soluzione completa per cliniche dentali:", "Il nostro obiettivo è semplice: far trovare la clinica ai pazienti giusti e trasformare la visibilità in richieste e appuntamenti reali.", "Sarò lieto di mostrare come funziona il sistema e come adattarlo alla vostra clinica. Sareste disponibili per un incontro di 20–30 minuti la prossima settimana?", "Cordiali saluti"],
"Dutch": ["Een kort idee voor uw kliniek", "Geachte tandheelkundige professionals,", "Tijdens een zoektocht naar tandartspraktijken in de regio via Google Maps kwam ik uw praktijk tegen. Na uw online aanwezigheid te hebben bekeken, leek het mij nuttig om mijzelf en onze diensten kort voor te stellen.", "Ik ben Eduardo Villodre, oprichter van ConsthruAds en MEDIF LTD in Cyprus. Ik bespreek graag hoe wij uw kliniek kunnen helpen meer patiënten aan te trekken en haar digitale aanwezigheid te versterken.", "Digitale groei en patiëntenwerving voor tandartspraktijken", "ConsthruAds helpt tandartspraktijken hun online aanwezigheid om te zetten in een constante bron van nieuwe patiëntaanvragen.", "Website en online aanwezigheid", "Wij creëren een professionele, conversiegerichte digitale aanwezigheid die behandelingen duidelijk toont, vertrouwen opbouwt en contact of een afspraak eenvoudig maakt.", "Patiëntenwerving", "Wij maken gerichte digitale campagnes die mensen bereiken die tandheelkundige behandelingen zoeken en hun interesse omzetten in gekwalificeerde aanvragen.", "Bekijk hier onze complete oplossing voor tandartspraktijken:", "Ons doel is eenvoudig: zorgen dat de juiste patiënten uw kliniek vinden en die zichtbaarheid omzetten in echte aanvragen en afspraken.", "Ik laat graag zien hoe het systeem werkt en hoe het aan uw kliniek kan worden aangepast. Heeft u volgende week 20–30 minuten tijd?", "Met vriendelijke groet"],
"Greek": ["Μια σύντομη ιδέα για την κλινική σας", "Αγαπητοί επαγγελματίες οδοντιατρικής,", "Αναζητώντας οδοντιατρικές κλινικές στην περιοχή μέσω Google Maps, βρήκα την κλινική σας. Αφού είδα την online παρουσία σας, σκέφτηκα να συστηθώ και να εξηγήσω σύντομα τι κάνουμε.", "Είμαι ο Eduardo Villodre, ιδρυτής των ConsthruAds και MEDIF LTD με έδρα την Κύπρο. Θα χαρώ να συζητήσουμε πώς μπορούμε να βοηθήσουμε την κλινική σας να προσελκύσει περισσότερους ασθενείς και να ενισχύσει την ψηφιακή της παρουσία.", "Ψηφιακή ανάπτυξη και προσέλκυση ασθενών για οδοντιατρικές κλινικές", "Στην ConsthruAds βοηθάμε τις οδοντιατρικές κλινικές να μετατρέψουν την online παρουσία τους σε σταθερή πηγή νέων αιτημάτων.", "Ιστοσελίδα και online παρουσία", "Δημιουργούμε επαγγελματική ψηφιακή παρουσία που παρουσιάζει καθαρά τις θεραπείες, χτίζει εμπιστοσύνη και διευκολύνει την επικοινωνία ή το ραντεβού.", "Προσέλκυση ασθενών", "Δημιουργούμε στοχευμένες ψηφιακές καμπάνιες για άτομα που αναζητούν οδοντιατρικές θεραπείες και μετατρέπουμε το ενδιαφέρον τους σε ποιοτικά αιτήματα.", "Δείτε εδώ την ολοκληρωμένη λύση μας:", "Στόχος μας είναι οι σωστοί ασθενείς να βρίσκουν την κλινική σας και η προβολή να μετατρέπεται σε πραγματικά αιτήματα και ραντεβού.", "Θα χαρώ να σας δείξω το σύστημα και πώς προσαρμόζεται στην κλινική σας. Θα είχατε 20–30 λεπτά την επόμενη εβδομάδα;", "Με εκτίμηση"],
"Polish": ["Krótki pomysł dla Państwa kliniki", "Szanowni Państwo,", "Podczas wyszukiwania klinik stomatologicznych w okolicy w Google Maps znalazłem Państwa placówkę. Po zapoznaniu się z jej obecnością online pomyślałem, że warto krótko przedstawić siebie i naszą działalność.", "Nazywam się Eduardo Villodre i jestem założycielem ConsthruAds oraz MEDIF LTD z siedzibą na Cyprze. Chętnie omówię, jak możemy pomóc klinice pozyskać więcej pacjentów i wzmocnić jej obecność cyfrową.", "Rozwój cyfrowy i pozyskiwanie pacjentów dla klinik stomatologicznych", "Pomagamy klinikom stomatologicznym przekształcić obecność online w stałe źródło nowych zapytań pacjentów.", "Strona internetowa i obecność online", "Tworzymy profesjonalną obecność cyfrową, która jasno przedstawia zabiegi, buduje zaufanie i ułatwia kontakt lub umówienie wizyty.", "Pozyskiwanie pacjentów", "Tworzymy ukierunkowane kampanie cyfrowe docierające do osób szukających leczenia stomatologicznego i zamieniamy ich zainteresowanie w wartościowe zapytania.", "Pełne rozwiązanie dla klinik stomatologicznych można zobaczyć tutaj:", "Nasz cel jest prosty: pomóc właściwym pacjentom znaleźć klinikę i zamienić widoczność w realne zapytania i wizyty.", "Chętnie pokażę działanie systemu i sposób dopasowania go do kliniki. Czy znajdą Państwo 20–30 minut w przyszłym tygodniu?", "Z poważaniem"],
"Romanian": ["O idee rapidă pentru clinica dumneavoastră", "Stimați profesioniști din domeniul stomatologic,", "Căutând clinici stomatologice din zonă pe Google Maps, am găsit clinica dumneavoastră. După ce am analizat prezența sa online, m-am gândit să mă prezint și să explic pe scurt ce facem.", "Sunt Eduardo Villodre, fondatorul ConsthruAds și MEDIF LTD, cu sediul în Cipru. Aș fi încântat să discutăm cum putem ajuta clinica să atragă mai mulți pacienți și să își consolideze prezența digitală.", "Creștere digitală și atragerea pacienților pentru clinici stomatologice", "Ajutăm clinicile stomatologice să transforme prezența online într-o sursă constantă de noi solicitări.", "Site web și prezență online", "Creăm o prezență digitală profesională care prezintă clar tratamentele, inspiră încredere și facilitează contactul sau programarea.", "Atragerea pacienților", "Creăm campanii digitale direcționate către persoanele care caută tratamente stomatologice și transformăm interesul în solicitări calificate.", "Vedeți aici soluția noastră completă:", "Scopul nostru este simplu: pacienții potriviți să găsească clinica, iar vizibilitatea să devină solicitări și programări reale.", "Vă pot arăta cum funcționează sistemul și cum se adaptează clinicii. Aveți 20–30 de minute disponibile săptămâna viitoare?", "Cu stimă"],
"Czech": ["Krátký nápad pro vaši kliniku", "Vážení stomatologičtí odborníci,", "Při hledání zubních klinik v okolí na Google Maps jsem našel vaši kliniku. Po zhlédnutí její online prezentace jsem se rozhodl krátce představit sebe a naši práci.", "Jmenuji se Eduardo Villodre a jsem zakladatelem ConsthruAds a MEDIF LTD se sídlem na Kypru. Rád proberu, jak můžeme klinice pomoci získat více pacientů a posílit digitální prezentaci.", "Digitální růst a získávání pacientů pro zubní kliniky", "Pomáháme zubním klinikám proměnit online prezentaci ve stálý zdroj nových poptávek pacientů.", "Web a online prezentace", "Vytváříme profesionální digitální prezentaci, která jasně ukazuje ošetření, buduje důvěru a usnadňuje kontakt nebo objednání.", "Získávání pacientů", "Vytváříme cílené digitální kampaně pro lidi hledající zubní ošetření a měníme jejich zájem v kvalifikované poptávky.", "Naše kompletní řešení najdete zde:", "Cíl je jednoduchý: pomoci správným pacientům najít kliniku a proměnit viditelnost ve skutečné poptávky a termíny.", "Rád ukážu, jak systém funguje a jak jej přizpůsobit klinice. Měli byste příští týden 20–30 minut?", "S pozdravem"],
"Slovak": ["Krátky nápad pre vašu kliniku", "Vážení stomatologickí odborníci,", "Pri hľadaní zubných kliník v okolí na Google Maps som našiel vašu kliniku. Po prezretí jej online prezentácie som sa rozhodol krátko predstaviť seba a našu prácu.", "Som Eduardo Villodre, zakladateľ ConsthruAds a MEDIF LTD so sídlom na Cypre. Rád prediskutujem, ako môžeme klinike pomôcť získať viac pacientov a posilniť digitálnu prezentáciu.", "Digitálny rast a získavanie pacientov pre zubné kliniky", "Pomáhame zubným klinikám premeniť online prítomnosť na stály zdroj nových otázok pacientov.", "Web a online prítomnosť", "Vytvárame profesionálnu digitálnu prezentáciu, ktorá jasne ukazuje ošetrenia, buduje dôveru a uľahčuje kontakt alebo objednanie.", "Získavanie pacientov", "Vytvárame cielené digitálne kampane pre ľudí hľadajúcich zubné ošetrenie a meníme ich záujem na kvalifikované otázky.", "Naše kompletné riešenie nájdete tu:", "Cieľ je jednoduchý: pomôcť správnym pacientom nájsť kliniku a premeniť viditeľnosť na skutočné otázky a termíny.", "Rád ukážem fungovanie systému a jeho prispôsobenie klinike. Mali by ste budúci týždeň 20–30 minút?", "S pozdravom"],
"Hungarian": ["Egy gyors ötlet a klinikája számára", "Tisztelt Fogászati Szakemberek!", "A Google Térképen a környék fogászati klinikáit keresve találtam rá az Önök rendelőjére. Az online megjelenés áttekintése után szeretném röviden bemutatni magam és a munkánkat.", "Eduardo Villodre vagyok, a ciprusi ConsthruAds és MEDIF LTD alapítója. Örömmel egyeztetek arról, hogyan segíthetünk több pácienst elérni és erősíteni a digitális jelenlétet.", "Digitális növekedés és páciensszerzés fogászati klinikáknak", "Segítünk a fogászati klinikáknak online jelenlétüket új páciensmegkeresések folyamatos forrásává alakítani.", "Weboldal és online jelenlét", "Professzionális digitális jelenlétet hozunk létre, amely bemutatja a kezeléseket, bizalmat épít és megkönnyíti a kapcsolatfelvételt vagy időpontkérést.", "Páciensszerzés", "Célzott digitális kampányokkal érjük el a fogászati kezelést keresőket, és érdeklődésüket minősített megkeresésekké alakítjuk.", "Teljes megoldásunk itt tekinthető meg:", "Célunk, hogy a megfelelő páciensek megtalálják a klinikát, és a láthatóság valódi megkereséseket és időpontokat eredményezzen.", "Szívesen bemutatom a rendszert és annak klinikára szabását. Lenne 20–30 perce a jövő héten?", "Üdvözlettel"],
"Croatian": ["Kratka ideja za vašu kliniku", "Poštovani stomatološki stručnjaci,", "Pretražujući stomatološke klinike u okolici na Google Mapsu, pronašao sam vašu kliniku. Nakon pregleda vaše internetske prisutnosti želio sam ukratko predstaviti sebe i naš rad.", "Ja sam Eduardo Villodre, osnivač tvrtki ConsthruAds i MEDIF LTD sa sjedištem na Cipru. Rado bih razgovarao o tome kako možemo pomoći klinici privući više pacijenata i ojačati digitalnu prisutnost.", "Digitalni rast i privlačenje pacijenata za stomatološke klinike", "Pomažemo stomatološkim klinikama pretvoriti internetsku prisutnost u stalan izvor novih upita pacijenata.", "Web-stranica i internetska prisutnost", "Stvaramo profesionalnu digitalnu prisutnost koja jasno predstavlja tretmane, gradi povjerenje i olakšava kontakt ili rezervaciju termina.", "Privlačenje pacijenata", "Izrađujemo ciljane digitalne kampanje za osobe koje traže stomatološke tretmane i pretvaramo interes u kvalitetne upite.", "Naše cjelovito rješenje možete vidjeti ovdje:", "Cilj je jednostavan: pomoći pravim pacijentima pronaći kliniku i pretvoriti vidljivost u stvarne upite i termine.", "Rado ću pokazati kako sustav radi i kako se prilagođava klinici. Imate li 20–30 minuta sljedeći tjedan?", "Srdačan pozdrav"],
"Bulgarian": ["Кратка идея за вашата клиника", "Уважаеми стоматолози,", "Докато търсех стоматологични клиники в района чрез Google Maps, попаднах на вашата клиника. След като разгледах онлайн присъствието ви, реших накратко да представя себе си и нашата работа.", "Казвам се Eduardo Villodre и съм основател на ConsthruAds и MEDIF LTD със седалище в Кипър. С удоволствие бих обсъдил как можем да помогнем на клиниката да привлече повече пациенти и да укрепи дигиталното си присъствие.", "Дигитален растеж и привличане на пациенти за стоматологични клиники", "Помагаме на стоматологичните клиники да превърнат онлайн присъствието си в постоянен източник на нови запитвания.", "Уебсайт и онлайн присъствие", "Създаваме професионално дигитално присъствие, което ясно представя леченията, изгражда доверие и улеснява контакта или записването на час.", "Привличане на пациенти", "Създаваме целеви дигитални кампании за хора, които търсят стоматологично лечение, и превръщаме интереса им в качествени запитвания.", "Вижте цялостното ни решение тук:", "Целта е правилните пациенти да намерят клиниката и видимостта да се превърне в реални запитвания и часове.", "С удоволствие ще покажа системата и как се адаптира към клиниката. Имате ли 20–30 минути следващата седмица?", "С уважение"],
"Arabic": ["فكرة سريعة لعيادتكم", "السادة أطباء وفرق طب الأسنان المحترمون،", "أثناء بحثي في خرائط Google عن عيادات الأسنان في المنطقة، وجدت عيادتكم. وبعد الاطلاع على حضوركم الرقمي، رأيت أنه من المفيد أن أعرّف بنفسي وبما نقدمه.", "أنا Eduardo Villodre، مؤسس ConsthruAds وMEDIF LTD في قبرص. يسعدني أن نناقش كيف يمكننا مساعدة عيادتكم على جذب مزيد من المرضى وتعزيز حضورها الرقمي.", "النمو الرقمي واستقطاب المرضى لعيادات الأسنان", "نساعد عيادات الأسنان على تحويل حضورها عبر الإنترنت إلى مصدر مستمر لاستفسارات المرضى الجدد.", "الموقع والحضور الرقمي", "نبني حضورًا رقميًا احترافيًا يوضح العلاجات، ويعزز الثقة، ويسهّل التواصل أو طلب موعد.", "استقطاب المرضى", "ننشئ حملات رقمية موجهة للوصول إلى الباحثين عن علاجات الأسنان وتحويل اهتمامهم إلى استفسارات مؤهلة.", "يمكنكم الاطلاع على حلنا المتكامل هنا:", "هدفنا بسيط: مساعدة المرضى المناسبين على العثور على عيادتكم وتحويل الظهور إلى استفسارات ومواعيد حقيقية.", "يسعدني عرض النظام ومناقشة تكييفه لعيادتكم. هل يناسبكم اجتماع لمدة 20–30 دقيقة الأسبوع المقبل؟", "مع أطيب التحيات"],
"Russian": ["Короткая идея для вашей клиники", "Уважаемые специалисты стоматологии!", "При поиске стоматологических клиник в вашем районе на Google Maps я увидел вашу клинику. Ознакомившись с её присутствием в интернете, я решил кратко представить себя и нашу работу.", "Меня зовут Eduardo Villodre, я основатель ConsthruAds и MEDIF LTD на Кипре. Буду рад обсудить, как мы можем помочь клинике привлечь больше пациентов и усилить цифровое присутствие.", "Цифровой рост и привлечение пациентов для стоматологических клиник", "Мы помогаем стоматологическим клиникам превратить присутствие в интернете в постоянный источник новых обращений пациентов.", "Сайт и присутствие в интернете", "Мы создаём профессиональное цифровое присутствие, которое понятно представляет услуги, укрепляет доверие и упрощает обращение или запись.", "Привлечение пациентов", "Мы создаём целевые цифровые кампании для людей, которые ищут стоматологическое лечение, и превращаем интерес в качественные обращения.", "Наше комплексное решение можно посмотреть здесь:", "Цель проста: помочь нужным пациентам найти клинику и превратить видимость в реальные обращения и записи.", "Буду рад показать работу системы и обсудить её адаптацию. Найдётся ли у вас 20–30 минут на следующей неделе?", "С уважением"],
"Albanian": ["Një ide e shkurtër për klinikën tuaj", "Të nderuar profesionistë të stomatologjisë,", "Duke kërkuar klinika dentare në zonë në Google Maps, gjeta klinikën tuaj. Pasi pashë praninë tuaj online, mendova të prezantohem dhe të shpjegoj shkurt çfarë bëjmë.", "Jam Eduardo Villodre, themelues i ConsthruAds dhe MEDIF LTD në Qipro. Do të isha i lumtur të diskutonim si mund ta ndihmojmë klinikën të tërheqë më shumë pacientë dhe të forcojë praninë digjitale.", "Rritje digjitale dhe tërheqje pacientësh për klinikat dentare", "Ndihmojmë klinikat dentare ta kthejnë praninë online në një burim të vazhdueshëm kërkesash të reja.", "Faqja dhe prania online", "Krijojmë prani digjitale profesionale që paraqet qartë trajtimet, ndërton besim dhe lehtëson kontaktin ose rezervimin.", "Tërheqja e pacientëve", "Krijojmë fushata digjitale të synuara për njerëzit që kërkojnë trajtime dentare dhe e kthejmë interesin në kërkesa të kualifikuara.", "Zgjidhjen tonë të plotë mund ta shihni këtu:", "Qëllimi është i thjeshtë: pacientët e duhur të gjejnë klinikën dhe dukshmëria të kthehet në kërkesa e takime reale.", "Do të isha i lumtur t’ju tregoj sistemin dhe përshtatjen e tij. A keni 20–30 minuta javën e ardhshme?", "Me respekt"],
}

LANG_CODE = {"English":"en", "Spanish":"es", "French":"fr", "German":"de", "Greek":"el", "Arabic":"ar", "Russian":"ru"}

def q(value):
    return "'" + value.replace("'", "''") + "'"

def body(values, language):
    code = LANG_CODE.get(language, "en")
    url = f"https://www.consthruads.com/dentist/?lang={code}"
    html = "".join([
        f"<p>{values[1]}</p>", f"<p>{values[2]}</p>", f"<p>{values[3]}</p>",
        f"<p>🦷 <strong>{values[4]}</strong></p><p>{values[5]}</p>",
        f"<p>🌐 <strong>{values[6]}</strong></p><p>{values[7]}</p>",
        f"<p>🎯 <strong>{values[8]}</strong></p><p>{values[9]}</p>",
        f'<p>{values[10]}</p><p><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></p>',
        f"<p>{values[11]}</p><p>{values[12]}</p>",
        f"<p>{values[13]},<br>Eduardo Villodre<br>Founder &amp; CEO – ConsthruAds<br>Founder – MEDIF LTD<br>📞 +34 633 30 38 57</p>",
    ])
    return f'<div dir="rtl">{html}</div>' if language == "Arabic" else html

assigned = {}
groups = {language: [] for language in T}
for country in COUNTRIES:
    matches = [language for language, countries in SPECIAL.items() if country in countries]
    if len(matches) > 1:
        raise RuntimeError(f"Duplicate language mapping: {country}: {matches}")
    language = matches[0] if matches else "English"
    assigned[country] = language
    groups[language].append(country)
if len(assigned) != len(COUNTRIES) or set(assigned) != set(COUNTRIES):
    raise RuntimeError("Country mapping is incomplete")

mapping = []
for language, countries in groups.items():
    for country in countries:
        display = "USA" if country == "United States" else country
        mapping.append((language, f"{display} odontologist leads *"))

definitions = []
for language, values in T.items():
    definitions.append((language, f"odontologist {language.lower()} no-repeat **", f"Dental Growth & Patient Acquisition - {language} (No Repeat)", values[0], body(values, language)))

mapping_values = ",".join(f"({q(a)},{q(b)})" for a, b in mapping)
definition_values = ",".join(f"({q(a)},{q(b)},{q(c)},{q(d)},{q(e)})" for a, b, c, d, e in definitions)

sql = f"""\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(88110019);
CREATE TEMP TABLE lang_map(language text, list_name text);
INSERT INTO lang_map VALUES {mapping_values};
CREATE TEMP TABLE lang_defs(language text, group_name text, campaign_name text, subject text, body text);
INSERT INTO lang_defs VALUES {definition_values};
DO $$ BEGIN
 IF (SELECT COUNT(*) FROM lang_map) <> {len(COUNTRIES)} OR (SELECT COUNT(DISTINCT list_name) FROM lang_map) <> {len(COUNTRIES)} THEN RAISE EXCEPTION 'Invalid country map'; END IF;
 IF (SELECT COUNT(*) FROM lists l JOIN lang_map m ON m.list_name=l.name) <> {len(COUNTRIES)} THEN RAISE EXCEPTION 'Missing production source list'; END IF;
 IF NOT EXISTS (SELECT 1 FROM lists WHERE id=1695) THEN RAISE EXCEPTION 'Previous-send exclusion list 1695 missing'; END IF;
END $$;
CREATE TEMP TABLE eligible AS
 SELECT DISTINCT d.language,s.id subscriber_id
 FROM lang_defs d JOIN lang_map m ON m.language=d.language JOIN lists src ON src.name=m.list_name
 JOIN subscriber_lists sl ON sl.list_id=src.id JOIN subscribers s ON s.id=sl.subscriber_id
 WHERE sl.status='confirmed' AND s.status='enabled'
   AND NOT EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id)
   AND NOT EXISTS(SELECT 1 FROM subscriber_lists u WHERE u.subscriber_id=s.id AND u.status='unsubscribed')
   AND NOT EXISTS(SELECT 1 FROM subscriber_lists old WHERE old.list_id=1695 AND old.subscriber_id=s.id);
CREATE TEMP TABLE active_defs AS SELECT d.* FROM lang_defs d WHERE EXISTS(SELECT 1 FROM eligible e WHERE e.language=d.language);
INSERT INTO lists(uuid,name,type,optin,tags,description)
 SELECT gen_random_uuid(),d.group_name,'private','single',ARRAY[]::varchar[],'Strict odontologist audience; excludes every campaign 19 recipient; '||d.language
 FROM active_defs d WHERE NOT EXISTS(SELECT 1 FROM lists l WHERE l.name=d.group_name);
DELETE FROM subscriber_lists sl USING lists l,active_defs d
 WHERE sl.list_id=l.id AND l.name=d.group_name AND NOT EXISTS(SELECT 1 FROM eligible e WHERE e.language=d.language AND e.subscriber_id=sl.subscriber_id);
INSERT INTO subscriber_lists(subscriber_id,list_id,status)
 SELECT e.subscriber_id,l.id,'confirmed'::subscription_status FROM eligible e JOIN active_defs d ON d.language=e.language JOIN lists l ON l.name=d.group_name
 ON CONFLICT(subscriber_id,list_id) DO UPDATE SET status='confirmed'::subscription_status;
INSERT INTO campaigns(uuid,name,subject,from_email,body,content_type,status,type,messenger,template_id)
 SELECT gen_random_uuid(),d.campaign_name,d.subject,(SELECT from_email FROM campaigns WHERE id=19),d.body,'html','draft','regular','email',1
 FROM active_defs d WHERE NOT EXISTS(SELECT 1 FROM campaigns c WHERE c.name=d.campaign_name);
DO $$ BEGIN IF EXISTS(SELECT 1 FROM campaigns c JOIN active_defs d ON d.campaign_name=c.name WHERE c.status<>'draft' OR c.sent<>0) THEN RAISE EXCEPTION 'Campaign name collision with non-draft'; END IF; END $$;
UPDATE campaigns c SET subject=d.subject,from_email=(SELECT from_email FROM campaigns WHERE id=19),body=d.body,content_type='html',messenger='email',template_id=1,updated_at=now()
 FROM active_defs d WHERE c.name=d.campaign_name AND c.status='draft' AND c.sent=0;
DELETE FROM campaign_lists cl USING campaigns c,active_defs d WHERE cl.campaign_id=c.id AND c.name=d.campaign_name;
INSERT INTO campaign_lists(campaign_id,list_id) SELECT c.id,l.id FROM campaigns c JOIN active_defs d ON d.campaign_name=c.name JOIN lists l ON l.name=d.group_name;
WITH stats AS (
 SELECT c.id,COUNT(DISTINCT e.subscriber_id)::integer n,MAX(e.subscriber_id)::integer max_id
 FROM campaigns c JOIN active_defs d ON d.campaign_name=c.name JOIN eligible e ON e.language=d.language GROUP BY c.id
) UPDATE campaigns c SET to_send=stats.n,max_subscriber_id=stats.max_id,last_subscriber_id=0 FROM stats WHERE c.id=stats.id;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM eligible e JOIN subscriber_lists old ON old.list_id=1695 AND old.subscriber_id=e.subscriber_id) THEN RAISE EXCEPTION 'Previous recipient overlap'; END IF;
 IF EXISTS(SELECT 1 FROM eligible e JOIN bounces b ON b.subscriber_id=e.subscriber_id) THEN RAISE EXCEPTION 'Bounce in new audience'; END IF;
END $$;
SELECT json_build_object(
 'source_countries',(SELECT COUNT(*) FROM lang_map),
 'previous_campaign_recipients',(SELECT COUNT(*) FROM subscriber_lists WHERE list_id=1695),
 'languages_created',(SELECT COUNT(*) FROM active_defs),
 'audiences',(SELECT json_object_agg(d.language,(SELECT COUNT(*) FROM eligible e WHERE e.language=d.language)) FROM active_defs d),
 'drafts',(SELECT json_object_agg(c.id,json_build_object('name',c.name,'targets',c.to_send,'status',c.status,'sent',c.sent)) FROM campaigns c JOIN active_defs d ON d.campaign_name=c.name),
 'total_new_targets',(SELECT COUNT(DISTINCT subscriber_id) FROM eligible),
 'overlap_with_previous',(SELECT COUNT(*) FROM eligible e JOIN subscriber_lists old ON old.list_id=1695 AND old.subscriber_id=e.subscriber_id),
 'unsafe',(SELECT COUNT(*) FROM eligible e JOIN subscribers s ON s.id=e.subscriber_id WHERE s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id))
);
COMMIT;
"""

password = os.environ["LISTMONK_VPS_PASSWORD"]
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(os.environ.get("VPS_HOST", "187.127.70.251"), username="root", password=password, timeout=20)
payload = base64.b64encode(sql.encode("utf-8")).decode("ascii")
command = f'''docker exec listmonk-production-postgres-1 sh -lc 'echo {payload} | base64 -d | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' '''
_, stdout, stderr = client.exec_command(command, timeout=1200)
output = stdout.read().decode("utf-8")
error = stderr.read().decode("utf-8")
client.close()
if error.strip():
    raise RuntimeError(error)
rows = [line for line in output.splitlines() if line.startswith("{")]
print(json.dumps(json.loads(rows[-1]), ensure_ascii=True, indent=2))
