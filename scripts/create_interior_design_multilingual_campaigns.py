#!/usr/bin/env python3
"""Create the core localized interior-design audiences and draft campaigns.

Italian and Portuguese are split by fix_interior_design_extended_languages.py
because the live selector adds them dynamically after the base HTML loads.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse

import paramiko


# subject, greeting, maps, audit, intro, title1, copy1, title2, copy2, link_intro, close, regards
T = {
    "English": [
        "A quick idea for your studio", "Hi there,",
        "I was looking through Google Maps for interior designers, interior architects, architecture studios and construction companies in the area and came across your business, so I thought I’d reach out.",
        "I had a look at your website and noticed a few areas that could be improved, particularly the <strong>mobile experience, performance and some of the content</strong>. These are things we could potentially fix in less than two hours.",
        "We’re a software development company, and this is just a very brief introduction to two solutions we offer for professionals and companies working in interior design, architecture, renovation and construction:",
        "Interior Design Websites", "Rebranding, redesigning or improving your existing website to give your studio or company a more modern, professional and visually impressive online presence. AI is changing the game in web design, and some of the new designs and possibilities are absolutely stunning — especially for highly visual industries such as interior design and architecture.",
        "Custom Studio Software", "Custom software to manage client enquiries, projects, follow-ups, proposals, invoices and other day-to-day processes in one place, built around the way your business actually works.",
        "You can have a quick look at both solutions here:", "If it looks relevant to your studio or company, I’d be happy to have a quick chat.", "Kind regards",
    ],
    "Spanish": [
        "Una idea rápida para su estudio", "Hola:",
        "Estaba buscando en Google Maps diseñadores de interiores, arquitectos de interiores, estudios de arquitectura y empresas de construcción de la zona, y encontré su negocio, así que pensé en ponerme en contacto.",
        "He revisado su sitio web y he observado algunas áreas que podrían mejorarse, especialmente la <strong>experiencia móvil, el rendimiento y parte del contenido</strong>. Son aspectos que potencialmente podríamos corregir en menos de dos horas.",
        "Somos una empresa de desarrollo de software y esta es solo una presentación muy breve de dos soluciones que ofrecemos a profesionales y empresas de interiorismo, arquitectura, renovación y construcción:",
        "Sitios web para interiorismo", "Renovamos la imagen, rediseñamos o mejoramos su sitio web actual para dar a su estudio o empresa una presencia online más moderna, profesional y visualmente impactante. La IA está cambiando las reglas del juego en el diseño web y algunos de los nuevos diseños y posibilidades son absolutamente impresionantes, especialmente para sectores tan visuales como el interiorismo y la arquitectura.",
        "Software personalizado para estudios", "Software personalizado para gestionar consultas de clientes, proyectos, seguimientos, propuestas, facturas y otros procesos cotidianos en un solo lugar, desarrollado en torno a la forma en que realmente funciona su negocio.",
        "Puede echar un vistazo rápido a ambas soluciones aquí:", "Si le parece relevante para su estudio o empresa, estaré encantado de mantener una breve conversación.", "Un cordial saludo",
    ],
    "Russian": [
        "Короткая идея для вашей студии", "Здравствуйте!",
        "Я искал в Google Maps дизайнеров интерьеров, интерьерных архитекторов, архитектурные бюро и строительные компании в вашем районе и увидел вашу компанию, поэтому решил связаться с вами.",
        "Я посмотрел ваш сайт и заметил несколько областей, которые можно улучшить, особенно <strong>мобильную версию, производительность и часть контента</strong>. Потенциально мы могли бы исправить это менее чем за два часа.",
        "Мы занимаемся разработкой программного обеспечения, и это лишь очень краткое представление двух решений для специалистов и компаний в сфере дизайна интерьеров, архитектуры, ремонта и строительства:",
        "Сайты для студий дизайна интерьеров", "Обновление бренда, редизайн или улучшение существующего сайта, чтобы обеспечить студии или компании более современное, профессиональное и визуально впечатляющее присутствие в интернете. ИИ меняет веб-дизайн, и некоторые новые решения действительно потрясают — особенно для таких визуальных отраслей, как дизайн интерьеров и архитектура.",
        "Индивидуальное программное обеспечение для студии", "Программное обеспечение для управления обращениями клиентов, проектами, последующими контактами, предложениями, счетами и другими ежедневными процессами в одном месте, созданное с учетом реальной работы вашего бизнеса.",
        "Кратко ознакомиться с обоими решениями можно здесь:", "Если это актуально для вашей студии или компании, буду рад коротко обсудить детали.", "С уважением",
    ],
    "Armenian": [
        "Արագ գաղափար ձեր ստուդիայի համար", "Բարև ձեզ,",
        "Google Maps-ում տարածքի ինտերիերի դիզայներներ, ինտերիերի ճարտարապետներ, ճարտարապետական ստուդիաներ և շինարարական ընկերություններ փնտրելիս գտա ձեր բիզնեսը և որոշեցի կապվել ձեզ հետ։",
        "Դիտեցի ձեր կայքը և նկատեցի բարելավման մի քանի հնարավորություն, հատկապես <strong>բջջային փորձառության, արագության և բովանդակության որոշ մասերի</strong> առումով։ Սրանք հնարավոր է շտկել երկու ժամից պակաս ժամանակում։",
        "Մենք ծրագրային ապահովման մշակման ընկերություն ենք, և սա ինտերիերի դիզայնի, ճարտարապետության, վերանորոգման ու շինարարության ոլորտի մասնագետների և ընկերությունների համար մեր երկու լուծումների շատ կարճ ներկայացումն է։",
        "Ինտերիերի դիզայնի կայքեր", "Ձեր առկա կայքի ռեբրենդինգ, վերաձևավորում կամ բարելավում՝ ստուդիային կամ ընկերությանը ավելի ժամանակակից, պրոֆեսիոնալ և տեսողականորեն տպավորիչ առցանց ներկայություն տալու համար։ Արհեստական բանականությունը փոխում է վեբ դիզայնը, և նոր հնարավորություններից մի քանիսը իսկապես տպավորիչ են, հատկապես ինտերիերի դիզայնի և ճարտարապետության նման տեսողական ոլորտներում։",
        "Անհատական ծրագրային ապահովում ստուդիայի համար", "Հաճախորդների հարցումները, նախագծերը, հետագա կապերը, առաջարկները, հաշիվները և ամենօրյա այլ գործընթացները մեկ վայրում կառավարելու ծրագրային ապահովում՝ կառուցված ձեր բիզնեսի իրական աշխատանքի շուրջ։",
        "Երկու լուծումներին կարող եք արագ ծանոթանալ այստեղ․", "Եթե սա համապատասխան է ձեր ստուդիայի կամ ընկերության համար, սիրով կզրուցեմ ձեզ հետ։", "Հարգանքով",
    ],
    "Georgian": [
        "მოკლე იდეა თქვენი სტუდიისთვის", "გამარჯობა,",
        "Google Maps-ზე თქვენს რეგიონში ინტერიერის დიზაინერებს, ინტერიერის არქიტექტორებს, არქიტექტურულ სტუდიებსა და სამშენებლო კომპანიებს ვეძებდი და თქვენი ბიზნესი ვიპოვე, ამიტომ გადავწყვიტე დაგკავშირებოდით.",
        "თქვენი ვებსაიტი გადავხედე და რამდენიმე გასაუმჯობესებელი მიმართულება შევნიშნე, განსაკუთრებით <strong>მობილური გამოცდილება, წარმადობა და კონტენტის ნაწილი</strong>. ამის გამოსწორება შესაძლოა ორ საათზე ნაკლებ დროში შევძლოთ.",
        "ჩვენ პროგრამული უზრუნველყოფის განვითარების კომპანია ვართ და ეს არის ორი გადაწყვეტის ძალიან მოკლე წარდგენა ინტერიერის დიზაინის, არქიტექტურის, რემონტისა და მშენებლობის სფეროში მომუშავე პროფესიონალებისა და კომპანიებისთვის:",
        "ინტერიერის დიზაინის ვებსაიტები", "არსებული ვებსაიტის რებრენდინგი, ხელახალი დიზაინი ან გაუმჯობესება, რათა თქვენს სტუდიას ან კომპანიას უფრო თანამედროვე, პროფესიონალური და ვიზუალურად შთამბეჭდავი ონლაინ παρουσία ჰქონდეს. ხელოვნური ინტელექტი ცვლის ვებდიზაინს და ახალი შესაძლებლობები განსაკუთრებით შთამბეჭდავია ინტერიერის დიზაინისა და არქიტექტურის მსგავს ვიზუალურ სფეროებში.",
        "სტუდიის ინდივიდუალური პროგრამული უზრუნველყოფა", "კლიენტების მოთხოვნების, პროექტების, შემდგომი კომუნიკაციის, შეთავაზებების, ინვოისებისა და ყოველდღიური პროცესების ერთ სივრცეში სამართავი პროგრამული უზრუნველყოფა, რომელიც თქვენი ბიზნესის რეალურ მუშაობას ერგება.",
        "ორივე გადაწყვეტა შეგიძლიათ მოკლედ იხილოთ აქ:", "თუ ეს თქვენი სტუდიისთვის ან კომპანიისთვის საინტერესოა, სიამოვნებით გავმართავ მოკლე საუბარს.", "პატივისცემით",
    ],
    "German": [
        "Eine kurze Idee für Ihr Studio", "Guten Tag,",
        "Bei der Suche nach Innenarchitekten, Interior Designern, Architekturbüros und Bauunternehmen in Ihrer Region auf Google Maps bin ich auf Ihr Unternehmen gestoßen und wollte mich deshalb kurz bei Ihnen melden.",
        "Ich habe mir Ihre Website angesehen und einige Bereiche entdeckt, die verbessert werden könnten, insbesondere die <strong>mobile Nutzung, die Performance und Teile der Inhalte</strong>. Diese Punkte könnten wir möglicherweise in weniger als zwei Stunden beheben.",
        "Wir sind ein Softwareentwicklungsunternehmen. Mit dieser kurzen Nachricht möchte ich Ihnen zwei Lösungen für Fachleute und Unternehmen aus Interior Design, Architektur, Renovierung und Bau vorstellen:",
        "Websites für Interior Design", "Rebranding, Neugestaltung oder Verbesserung Ihrer bestehenden Website, damit Ihr Studio oder Unternehmen online moderner, professioneller und visuell eindrucksvoller auftritt. KI verändert das Webdesign grundlegend, und einige der neuen Designs und Möglichkeiten sind besonders für visuelle Branchen wie Interior Design und Architektur beeindruckend.",
        "Individuelle Studio-Software", "Maßgeschneiderte Software, um Kundenanfragen, Projekte, Nachfassaktionen, Angebote, Rechnungen und weitere tägliche Abläufe an einem Ort zu verwalten — abgestimmt auf die tatsächliche Arbeitsweise Ihres Unternehmens.",
        "Einen kurzen Überblick über beide Lösungen finden Sie hier:", "Wenn dies für Ihr Studio oder Unternehmen interessant ist, freue ich mich über ein kurzes Gespräch.", "Mit freundlichen Grüßen",
    ],
    "French": [
        "Une idée rapide pour votre studio", "Bonjour,",
        "En recherchant sur Google Maps des designers d’intérieur, architectes d’intérieur, agences d’architecture et entreprises de construction dans votre région, j’ai découvert votre entreprise et j’ai donc souhaité vous contacter.",
        "J’ai consulté votre site web et remarqué plusieurs points qui pourraient être améliorés, notamment <strong>l’expérience mobile, les performances et certains contenus</strong>. Nous pourrions potentiellement corriger ces éléments en moins de deux heures.",
        "Nous sommes une société de développement logiciel et voici une très brève présentation de deux solutions destinées aux professionnels et entreprises de la décoration intérieure, de l’architecture, de la rénovation et de la construction :",
        "Sites web pour le design d’intérieur", "Refonte de marque, redesign ou amélioration de votre site actuel afin d’offrir à votre studio ou entreprise une présence en ligne plus moderne, professionnelle et visuellement remarquable. L’IA transforme la conception web et certaines nouvelles possibilités sont absolument impressionnantes, surtout pour les secteurs très visuels comme le design d’intérieur et l’architecture.",
        "Logiciel sur mesure pour studios", "Un logiciel personnalisé pour gérer au même endroit les demandes clients, projets, relances, propositions, factures et autres processus quotidiens, conçu autour du fonctionnement réel de votre entreprise.",
        "Vous pouvez découvrir rapidement les deux solutions ici :", "Si cela vous semble pertinent pour votre studio ou entreprise, je serais heureux d’échanger brièvement avec vous.", "Bien cordialement",
    ],
    "Arabic": [
        "فكرة سريعة لاستوديوكم", "مرحبًا،",
        "كنت أبحث في خرائط Google عن مصممي الديكور الداخلي ومهندسي العمارة الداخلية والاستوديوهات المعمارية وشركات البناء في المنطقة، ووجدت نشاطكم التجاري، لذلك رغبت في التواصل معكم.",
        "اطلعت على موقعكم ولاحظت بعض الجوانب التي يمكن تحسينها، وخصوصًا <strong>تجربة الهاتف المحمول والأداء وبعض المحتوى</strong>. ويمكننا على الأرجح معالجة هذه الأمور في أقل من ساعتين.",
        "نحن شركة لتطوير البرمجيات، وهذه مقدمة قصيرة جدًا عن حلّين نقدمهما للمتخصصين والشركات العاملة في التصميم الداخلي والعمارة والتجديد والبناء:",
        "مواقع للتصميم الداخلي", "إعادة بناء الهوية أو إعادة تصميم أو تحسين موقعكم الحالي لمنح الاستوديو أو الشركة حضورًا رقميًا أكثر حداثة واحترافية وتأثيرًا بصريًا. يغيّر الذكاء الاصطناعي عالم تصميم المواقع، وبعض التصاميم والإمكانات الجديدة مذهلة بالفعل، ولا سيما للقطاعات البصرية مثل التصميم الداخلي والعمارة.",
        "برمجيات مخصصة للاستوديو", "برمجيات مخصصة لإدارة استفسارات العملاء والمشاريع والمتابعة والعروض والفواتير وغيرها من العمليات اليومية في مكان واحد، ومصممة حول طريقة عمل نشاطكم الفعلية.",
        "يمكنكم الاطلاع سريعًا على الحلّين هنا:", "إذا كان ذلك مناسبًا لاستوديوكم أو شركتكم، فسيسعدني إجراء محادثة قصيرة معكم.", "مع أطيب التحيات",
    ],
    "Persian": [
        "یک ایده کوتاه برای استودیوی شما", "سلام،",
        "در Google Maps به دنبال طراحان داخلی، معماران داخلی، استودیوهای معماری و شرکت‌های ساختمانی منطقه بودم و با کسب‌وکار شما آشنا شدم؛ بنابراین تصمیم گرفتم با شما تماس بگیرم.",
        "وب‌سایت شما را بررسی کردم و چند بخش قابل بهبود دیدم، به‌ویژه <strong>تجربه موبایل، عملکرد و بخشی از محتوا</strong>. احتمالاً می‌توانیم این موارد را در کمتر از دو ساعت اصلاح کنیم.",
        "ما یک شرکت توسعه نرم‌افزار هستیم و این فقط معرفی بسیار کوتاهی از دو راهکار ما برای متخصصان و شرکت‌های فعال در طراحی داخلی، معماری، بازسازی و ساخت‌وساز است:",
        "وب‌سایت‌های طراحی داخلی", "بازطراحی هویت، طراحی مجدد یا بهبود وب‌سایت فعلی برای ایجاد حضوری مدرن‌تر، حرفه‌ای‌تر و از نظر بصری چشمگیرتر برای استودیو یا شرکت شما. هوش مصنوعی قواعد طراحی وب را تغییر می‌دهد و برخی طراحی‌ها و امکانات جدید، به‌ویژه برای صنایع بصری مانند طراحی داخلی و معماری، واقعاً خیره‌کننده‌اند.",
        "نرم‌افزار سفارشی استودیو", "نرم‌افزاری سفارشی برای مدیریت درخواست‌های مشتریان، پروژه‌ها، پیگیری‌ها، پیشنهادها، فاکتورها و سایر فرایندهای روزمره در یک محل، بر اساس شیوه واقعی کار کسب‌وکار شما.",
        "می‌توانید هر دو راهکار را به‌طور خلاصه اینجا ببینید:", "اگر این موضوع برای استودیو یا شرکت شما مرتبط است، خوشحال می‌شوم گفت‌وگوی کوتاهی داشته باشیم.", "با احترام",
    ],
    "Turkish": [
        "Stüdyonuz için kısa bir fikir", "Merhaba,",
        "Google Haritalar’da bölgedeki iç mimarları, iç mekân tasarımcılarını, mimarlık stüdyolarını ve inşaat şirketlerini araştırırken işletmenize rastladım ve size ulaşmak istedim.",
        "Web sitenizi inceledim ve özellikle <strong>mobil deneyim, performans ve bazı içerikler</strong> konusunda geliştirilebilecek birkaç alan fark ettim. Bunları potansiyel olarak iki saatten kısa sürede düzeltebiliriz.",
        "Biz bir yazılım geliştirme şirketiyiz. Bu mesaj, iç tasarım, mimarlık, yenileme ve inşaat alanında çalışan profesyoneller ve şirketler için sunduğumuz iki çözümün çok kısa bir tanıtımıdır:",
        "İç Tasarım Web Siteleri", "Stüdyonuza veya şirketinize daha modern, profesyonel ve görsel olarak etkileyici bir çevrimiçi varlık kazandırmak için mevcut web sitenizin yeniden markalandırılması, tasarlanması veya iyileştirilmesi. Yapay zekâ web tasarımını değiştiriyor ve yeni tasarım ve olanakların bazıları, özellikle iç tasarım ve mimarlık gibi görsel sektörler için gerçekten etkileyici.",
        "Özel Stüdyo Yazılımı", "Müşteri taleplerini, projeleri, takipleri, teklifleri, faturaları ve günlük süreçleri tek bir yerde yönetmek için işletmenizin gerçek çalışma biçimine göre geliştirilen özel yazılım.",
        "Her iki çözüme de buradan hızlıca göz atabilirsiniz:", "Stüdyonuz veya şirketiniz için uygun görünüyorsa kısa bir görüşme yapmaktan memnuniyet duyarım.", "Saygılarımla",
    ],
    "Greek": [
        "Μια σύντομη ιδέα για το στούντιό σας", "Γεια σας,",
        "Αναζητώντας στο Google Maps σχεδιαστές εσωτερικών χώρων, αρχιτέκτονες εσωτερικών χώρων, αρχιτεκτονικά γραφεία και κατασκευαστικές εταιρείες στην περιοχή, βρήκα την επιχείρησή σας και σκέφτηκα να επικοινωνήσω μαζί σας.",
        "Είδα την ιστοσελίδα σας και παρατήρησα ορισμένα σημεία που θα μπορούσαν να βελτιωθούν, ιδιαίτερα η <strong>εμπειρία σε κινητά, η απόδοση και μέρος του περιεχομένου</strong>. Θα μπορούσαμε ενδεχομένως να τα διορθώσουμε σε λιγότερο από δύο ώρες.",
        "Είμαστε εταιρεία ανάπτυξης λογισμικού και αυτή είναι μια πολύ σύντομη παρουσίαση δύο λύσεων που προσφέρουμε σε επαγγελματίες και εταιρείες στον σχεδιασμό εσωτερικών χώρων, την αρχιτεκτονική, την ανακαίνιση και τις κατασκευές:",
        "Ιστοσελίδες εσωτερικής διακόσμησης", "Ανανέωση επωνυμίας, επανασχεδιασμός ή βελτίωση της υπάρχουσας ιστοσελίδας σας, ώστε το στούντιο ή η εταιρεία σας να αποκτήσει πιο σύγχρονη, επαγγελματική και οπτικά εντυπωσιακή διαδικτυακή παρουσία. Η τεχνητή νοημοσύνη αλλάζει τον σχεδιασμό ιστοσελίδων και οι νέες δυνατότητες είναι εντυπωσιακές, ειδικά για οπτικούς κλάδους όπως το interior design και η αρχιτεκτονική.",
        "Εξατομικευμένο λογισμικό στούντιο", "Λογισμικό για τη διαχείριση αιτημάτων πελατών, έργων, επακόλουθων ενεργειών, προτάσεων, τιμολογίων και άλλων καθημερινών διαδικασιών σε ένα μέρος, σχεδιασμένο γύρω από τον πραγματικό τρόπο λειτουργίας της επιχείρησής σας.",
        "Μπορείτε να δείτε σύντομα και τις δύο λύσεις εδώ:", "Εάν είναι σχετικό με το στούντιο ή την εταιρεία σας, θα χαρώ να κάνουμε μια σύντομη συζήτηση.", "Με εκτίμηση",
    ],
}

CODES = {"English":"en", "Spanish":"es", "Russian":"ru", "Armenian":"hy", "Georgian":"ka", "German":"de", "French":"fr", "Arabic":"ar", "Persian":"fa", "Turkish":"tr", "Greek":"el"}

ENGLISH_LISTS = [
    "interior design english", "interior design polish", "interior design dutch",
    "interior design Norway", "interior design Finland", "interior design czech",
    "interior design hungarian", "interior design romanian", "interior design slovak", "interior design Denmark",
    "interior design croatian", "interior design bulgarian", "interior design Estonia", "interior design Lithuania",
    "interior design Latvia", "interior design albanian", "interior design Iceland", "interior design Brunei",
    "interior design Bhutan", "interior design Greenland", "interior design Svalbard and Jan Mayen",
]


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


FROM_EMAIL = os.environ.get("LISTMONK_FROM_EMAIL", "").strip()
if not FROM_EMAIL:
    raise RuntimeError("LISTMONK_FROM_EMAIL must contain the approved sender identity")


def make_html(language: str, values: list[str]) -> str:
    code = CODES[language]
    url = f"https://consthruads.com/interior-designers/?lang={code}"
    content = f'''<p>{values[1]}</p>
<p>{values[2]}</p>
<p>{values[3]}</p>
<p>{values[4]}</p>
<p><strong>1. {values[5]}</strong> – {values[6]}</p>
<p><strong>2. {values[7]}</strong> – {values[8]}</p>
<p>{values[9]}<br>
<a href="{url}" target="_blank" rel="noopener noreferrer">
{url}
</a></p>
<p>{values[10]}</p>
<p>{values[11]},<br>
Edward</p>
<p><a href="https://consthruads.com/?lang=en" target="_blank" rel="noopener noreferrer">https://consthruads.com/?lang=en</a></p>'''
    return f'<div dir="rtl">{content}</div>' if language in {"Arabic", "Persian"} else content


definitions = [(language, CODES[language], f"Interior Design Solutions - {language}", values[0], make_html(language, values), f"interior design {language.lower()}") for language, values in T.items()]
definition_values = ",".join(f"({quote(a)},{quote(b)},{quote(c)},{quote(d)},{quote(e)},{quote(f)})" for a,b,c,d,e,f in definitions)
english_values = ",".join(f"({quote(name)})" for name in ENGLISH_LISTS)

sql = f'''\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(82496681);
CREATE TEMP TABLE campaign_defs(language text,code text,campaign_name text,subject text,body text,group_name text);
INSERT INTO campaign_defs VALUES {definition_values};
CREATE TEMP TABLE english_lists(name text); INSERT INTO english_lists VALUES {english_values};
DO $$ BEGIN
 IF (SELECT COUNT(*) FROM campaign_defs)<>11 OR (SELECT COUNT(DISTINCT code) FROM campaign_defs)<>11 THEN RAISE EXCEPTION 'Invalid language definitions'; END IF;
 IF (SELECT COUNT(*) FROM lists l JOIN english_lists e ON e.name=l.name)<>(SELECT COUNT(*) FROM english_lists) THEN RAISE EXCEPTION 'Missing English source list'; END IF;
END $$;
INSERT INTO lists(uuid,name,type,optin,tags,description)
SELECT gen_random_uuid(),d.group_name,'private','single',ARRAY[]::varchar[],'Interior-design audience aligned to supported landing-page language '||d.code
FROM campaign_defs d WHERE d.language IN ('Armenian','Georgian','Persian','Turkish') AND NOT EXISTS(SELECT 1 FROM lists l WHERE l.name=d.group_name);
CREATE TEMP TABLE russian_source AS
SELECT sl.subscriber_id,COALESCE(s.attribs->>'country','') country
FROM subscriber_lists sl JOIN lists l ON l.id=sl.list_id JOIN subscribers s ON s.id=sl.subscriber_id
WHERE l.name='interior design russian' AND sl.status='confirmed';
INSERT INTO subscriber_lists(subscriber_id,list_id,status)
SELECT rs.subscriber_id,l.id,'confirmed'::subscription_status
FROM russian_source rs JOIN campaign_defs d ON d.language=CASE rs.country WHEN 'Armenia' THEN 'Armenian' WHEN 'Georgia' THEN 'Georgian' WHEN 'Azerbaijan' THEN 'Turkish' END
JOIN lists l ON l.name=d.group_name
WHERE rs.country IN ('Armenia','Georgia','Azerbaijan')
ON CONFLICT(subscriber_id,list_id) DO UPDATE SET status='confirmed'::subscription_status;
DELETE FROM subscriber_lists sl USING lists l,russian_source rs
WHERE sl.list_id=l.id AND l.name='interior design russian' AND sl.subscriber_id=rs.subscriber_id AND rs.country IN ('Armenia','Georgia','Azerbaijan');
CREATE TEMP TABLE campaign_targets(language text,list_name text);
INSERT INTO campaign_targets SELECT 'English',name FROM english_lists;
INSERT INTO campaign_targets VALUES
 ('Spanish','interior design spanish'),('Russian','interior design russian'),('Armenian','interior design armenian'),
 ('Georgian','interior design georgian'),('German','interior design german'),('French','interior design french'),
 ('French','interior design Luxembourg'),('Arabic','interior design arabic'),('Persian','interior design persian'),
 ('Turkish','interior design turkish'),('Greek','interior design greek');
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM campaign_targets t LEFT JOIN lists l ON l.name=t.list_name WHERE l.id IS NULL) THEN RAISE EXCEPTION 'Missing target list'; END IF;
 IF EXISTS(SELECT sl.subscriber_id FROM campaign_targets t JOIN lists l ON l.name=t.list_name JOIN subscriber_lists sl ON sl.list_id=l.id AND sl.status='confirmed' GROUP BY sl.subscriber_id HAVING COUNT(DISTINCT t.language)>1) THEN RAISE EXCEPTION 'Audience overlap between languages'; END IF;
END $$;
INSERT INTO campaigns(uuid,name,subject,from_email,body,content_type,status,type,messenger,template_id)
SELECT gen_random_uuid(),d.campaign_name,d.subject,{quote(FROM_EMAIL)},d.body,'html','draft','regular','email',1
FROM campaign_defs d WHERE NOT EXISTS(SELECT 1 FROM campaigns c WHERE c.name=d.campaign_name);
DO $$ BEGIN IF EXISTS(SELECT 1 FROM campaigns c JOIN campaign_defs d ON d.campaign_name=c.name WHERE c.status<>'draft' OR c.sent<>0) THEN RAISE EXCEPTION 'Campaign collision with non-draft'; END IF; END $$;
UPDATE campaigns c SET subject=d.subject,from_email={quote(FROM_EMAIL)},body=d.body,content_type='html',messenger='email',template_id=1,updated_at=now()
FROM campaign_defs d WHERE c.name=d.campaign_name AND c.status='draft' AND c.sent=0;
DELETE FROM campaign_lists cl USING campaigns c,campaign_defs d WHERE cl.campaign_id=c.id AND c.name=d.campaign_name;
INSERT INTO campaign_lists(campaign_id,list_id,list_name)
SELECT c.id,l.id,l.name FROM campaigns c JOIN campaign_defs d ON d.campaign_name=c.name JOIN campaign_targets t ON t.language=d.language JOIN lists l ON l.name=t.list_name;
WITH stats AS (
 SELECT c.id,COUNT(DISTINCT s.id)::integer n,COALESCE(MAX(s.id),0)::integer max_id
 FROM campaigns c JOIN campaign_defs d ON d.campaign_name=c.name JOIN campaign_targets t ON t.language=d.language JOIN lists l ON l.name=t.list_name
 LEFT JOIN subscriber_lists sl ON sl.list_id=l.id AND sl.status='confirmed' LEFT JOIN subscribers s ON s.id=sl.subscriber_id AND s.status='enabled' AND NOT EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id)
 GROUP BY c.id
) UPDATE campaigns c SET to_send=stats.n,max_subscriber_id=stats.max_id,last_subscriber_id=0 FROM stats WHERE c.id=stats.id;
SELECT json_build_object(
 'languages',(SELECT COUNT(*) FROM campaign_defs),
 'campaigns',(SELECT json_agg(json_build_object('id',c.id,'language',d.language,'code',d.code,'targets',c.to_send,'status',c.status,'sent',c.sent,'link_ok',position('interior-designers/?lang='||d.code in c.body)>0) ORDER BY c.id) FROM campaigns c JOIN campaign_defs d ON d.campaign_name=c.name),
 'total_unique_targets',(SELECT COUNT(DISTINCT sl.subscriber_id) FROM campaign_targets t JOIN lists l ON l.name=t.list_name JOIN subscriber_lists sl ON sl.list_id=l.id WHERE sl.status='confirmed'),
 'cross_language_overlap',(SELECT COUNT(*) FROM (SELECT sl.subscriber_id FROM campaign_targets t JOIN lists l ON l.name=t.list_name JOIN subscriber_lists sl ON sl.list_id=l.id AND sl.status='confirmed' GROUP BY sl.subscriber_id HAVING COUNT(DISTINCT t.language)>1) x),
 'unsafe',(SELECT COUNT(*) FROM campaign_targets t JOIN lists l ON l.name=t.list_name JOIN subscriber_lists sl ON sl.list_id=l.id JOIN subscribers s ON s.id=sl.subscriber_id WHERE sl.status='confirmed' AND (s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id))),
 'campaigns_not_draft',(SELECT COUNT(*) FROM campaigns c JOIN campaign_defs d ON d.campaign_name=c.name WHERE c.status<>'draft' OR c.sent<>0)
);
COMMIT;'''


def run(client, command: str, timeout: int = 1200) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    output, error = stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")
    if error.strip():
        raise RuntimeError(error)
    return output


def main() -> None:
    password = os.environ["LISTMONK_VPS_PASSWORD"]
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(os.environ["LISTMONK_VPS_HOST"], username="root", password=password, timeout=20)
    try:
        stamp = run(client, "date -u +%Y%m%d_%H%M%S").strip()
        backup = f"/root/listmonk-backups/pre_interior_design_campaigns_{stamp}.dump"
        run(client, f'''mkdir -p /root/listmonk-backups && docker exec listmonk-production-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > {backup} && test -s {backup}''')
        encoded = base64.b64encode(sql.encode()).decode()
        output = run(client, f'''docker exec listmonk-production-postgres-1 sh -lc 'echo {encoded} | base64 -d | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' ''')
        rows = [line for line in output.splitlines() if line.startswith("{")]
        result = json.loads(rows[-1]); result["backup"] = backup
        print(json.dumps(result, ensure_ascii=True, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
