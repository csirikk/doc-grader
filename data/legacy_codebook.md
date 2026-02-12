# Legacy Codebook

Aggregated sheets with legacy codes and explanations, used within IFJ & IPP for grading in 2024/25 from file `bp_data_v1.xlsx`, sheets:

- `ifj2425-klic`
- `ipp2425-task1-klic`
- `ipp2425-task2-klic`

## IFJ

| --- | --- |
| KA | chyby v KA, především větší míra nedeterminismu, chybějící důležité lexémy (např. ošetření komentářů atp.) |
| strukt. | nedostatky ve struktuře dokumentu (nejčastěji chybějící závěr) |
| PSA | chybějící nebo nedostatečný popis precedenční syntaktické analýzy |
| RP | chybějící popis rozdělení práce |
| GK | chybějící/nedostatečný popis generování kódu |
| 1. strana | chybějící informace na 1. straně dokumentace |
| LL | chyby a nedostatky v LL tabulce |
| LLT | chybějící nebo chybná LL tabulka (např. chybějící pravidla, ignorování množiny FOLLOW ve spojení s epsilon pravidly atd.) |
| typ. | typografické nedostatky (nejčastěji text nebyl zarovnán do bloku) |
| term. | nepřesná terminologie |
| SA | nedostatečný, chybějící nebo nepřesný popis syntaktické analýzy (např. tvrzení, že rekurzivní sestup implementují tak, že mají funkci pro každé pravidlo) |
| SAV | nedostatečný popis syntaktické analýzy výrazů |
| SéA | chybějící/nedostatečný popis sémantické analýzy (typicky není dobře, dostatečně konkrétně popsáno, co všechno se kontroluje) |
| PT | chybějící, chybná nebo nečitelná precedenční tabulka |
| TS | chybějící/nedostatečný popis tabulky symbolů či její implementace (např. slabý popis struktury tabulky – zda máte více tabulek nebo jednu atp.) |
| SHORT | nedostatečný, nekonkrétní popis řešení |
| STYLE | nesrozumitelné věty, dlouhá či těžko pochopitelná souvětí |
| gram. | gramatické chyby |
| LANG | míchání jazyků v rámci dokumentace (nejčastěji češtiny a slovenštiny) |
| HOV | použití hovorových výrazů, zbytečné používání anglických výrazů (např. pushnout, symtable, list, array) |
| BLOK | text není zarovnán do bloku |
| KAPTXT | dokumentace obsahuje více nadpisů hned za sebou |
| MEZ | špatné psaní mezer (např. kolem závorek a interpunkce) |
| SAZBA | alespoň identifikátory proměnných a funkcí se patří sázet písmem s jednotnou šířkou písmen (např. font Courier) |

## IPP1

Vysvětlivky k poznámkám:
Maximum je 100 minibodů (mb) u první úlohy, minimum je 0 mb. Limity srážek jsou pouze doporučení.
Zcela chybějící komentáře v parse.py jsou asi za -30 mb; za pravopisné chyby strhávejte až -30 mb)

| Identifikátor | Srážka [mb] | Popis |
| --- | --- | --- |
| Hodnocení dokumentace | | |
| STRUCT | -10 až -30 | chybí struktura nebo je nevhodná/nadpisy (stačí jediná úroveň) |
| SHORT | až -70 | moc krátké/nedostatečné; pokud student popsal vše potřebné, tak lze odpustit kratší rozsah |
| CH | á -5 (max. -30) | pravopisné chyby (vč. interpunkce) |
| FORMAT | většinou 0, ale až -20 | nedodrženy požadavky zadání a fóra (v případě, že obsahuje více než 2 stránky (nepočítejte do toho autorské-relevantní diagramy), tak označte oranžově) |
| MISSING | 0 mb | za text dokumentace zcela chybí (hodnotí se pouze komentáře 0-30mb, alespoň každá důležitá funkce by měla mít komentář k čemu je, zda a jak je použit nějaký rámec) |
| COPY | až -50 | text obsahuje úryvky ze zadání nebo cizí materiály (necitované obrázky z Internetu apod.) |
| STYLE | až -40 | stylizace vět, nečitelnost, nesrozumitelnost |
| FILO | až -50 | Zbyněk Křivka: lze využít i pro hodnocení zdrojových kódů chybí či nedostatečná filozofie návrhu skriptu (abstraktní popis struktury programu, co následuje za čím) |
| DOCTYPE | 0 až -20 | špatný typ souboru s dokumentací (vyžadujeme PDF nebo MarkDown, špatné jméno nepostihujeme) |
| TERM | á -5 až -10 | problematická terminologie (neobvyklá, nepřesná či přímo špatná) |
| CONTENT | až -40 | nevhodný obsah (popis časového průběhu řešení, vyjadřování pocitů, irelevantních myšlenek a nepodložených názorů) |
| IR | až -20 | Nepopsaná vnitřní reprezentace (nebo je nedostatečná; např. je napsáno jen to, že "přiřazení jsou ukládány do AST") |
| JAK | až -50 | technicky nedostatečný popis řešení (např. zda byly použity regulární výrazy/stavové řízení, parser-generator apod.) |
| Hodnocení skriptu | | |
| COMMENT | -10 až -30 | chybějící nebo nedostatečné komentáře ve zdrojovém textu (za všechny skripty dohromady), případné dostatečně samodokumentační identifikátory není třeba doplňovat komentáře. |
| SRCFORMAT | až -20 | opravdu velmi špatná štábní kultura zdrojového kódu (přehlednost, čitelnost kódu) |
| SPACETAB | bez postihu | Zbyněk Křivka: není nutné kontrolovat vždy, ale třeba jen namátkou kombinování mezer a tabelátorů k odsazování zdrojového textu (týká se především Pythonu) |
| DECOMPOSE | až -20 | skript není vůbec/dostatečně dekomponován na funkce (tolerujte velký switch ohledně výběru operačního kódu instrukce) |
| AUTHOR | bez postihu | ve skriptu chybí jméno autora |
| Upřesnění drobných chyb v dokumentaci | | |
| LANG | až -20 | míchání jazyků, anglické termíny (nejedná-li se o idenfitikátory ze zdrojového kódu) v českém textu |
| HOV | až -20 | hovorové výrazy nebo nevhodné slangové výrazy ("parsování" tolerujeme) |
| PRED | bez postihu | neslabičné předložky na konci řádku |
| FORM | až -10 | úprava, nekonzistentní velikost a typ písma apod. |
| BLOK | bez postihu | chybí zarovnaní do bloku místo méně pěkného zarovnání na prapor (doleva) (jen pro PDF) |
| KAPTXT | bez postihu | mezi nadpisem a jeho podnadpisem by měl být vždy nějaký text |
| ICH | bez postihu | ich-forma (psaní v první osobě jednotného čísla) není většinou vhodná pro programovou dokumentaci |
| MEZ | bez postihu | za otevírající nebo před zavírající závorku mezera nepatří |
| SAZBA | bez postihu | alespoň identifikátory proměnných a funkcí se patří sázet písmem s jednotnou šířkou písmen (např. font Courier) |
| Zcela bez připomínek | | |
| OK | | OK=vše OK, dávejte jen u hodnocení 100mb, kde nechcete autora na nic upozornit (aby nebyl komentář prázdný) |

Kromě těchto zkratek můžete psát i jakýkoli další oficiální komentář, který se zobrazí studentovi. |
Pokud chcete něco sdělit mě, tak použijte sloupec D a raději to nějak výrazně (červeně) podbarvěte. |
U slovenštiny byste měli stejně jako u češtiny posoudit pravopis (tj. až -30mb). |
U identifikátoru případně napište kolik minibodů ste srazili (třeba i 0, aby se studenti viděli, že jste na ně hodní). |
Neodevzdaná dokumentace je automaticky 0 mb. Pokud to uznáte za vhodné, lze udělit nějaké minibody za komentáře ve zdrojových kódech do výše cca 30mb.

### Bonusy

| OOP | až +20 | Pokud se vám líbí použití OOP ve skriptech včetně terminologický správného popisu v dokumentaci (strop 100 mb zůstává) |
| EX | až +20 | Pokud uvidíte, že někdo místo nepěkné kaskády if-else jsou použity výjimky (Exception a případně definoval i vlastní) pro správu chyb (strop 100 mb zůstává) |
| Rozšíření NVP | až +100 | Viz zadání; bodujte ve sloupci F; pokud uvedli NVP v souboru rozsireni, tak jsem podbarvil hodnotící pole zeleně. |
| SINGLETON | až -100 z NVP | Návrhový vzor Jedináček nebude v rámci NVP uznáván (viz zadání), takže je-li to jediný NV, tak nic. |
| NVPDOC | až -100 z NVP | Chybějící dokumentace rozšíření NVP (proč, kde, jak): (v případě, že to vypadá jako přidělávání práce - tj. uvedl NVP a není dokumentace, ani známky reálné implementace, tak strhávejte do záporu -50 i ze základu, což uveďte ve slovním hodnocení) |

## IPP 2

| Identifikátor | Srážka [mb] | Popis |
| --- | --- | --- |
| Statická analýza kódu pomocí PHPstan (cca 100 mb) | | |
| STN0 | -100 | nezvládá minimální požadovanou úroveň 0 (a bude postiženo i v automatických testech, v podstatě je projekt za 0, ale oprava je za -1b) |
| STN6 až STN1 | -10 až -60 | nezvládá některou z doporučených úrovní 1-6 |
| STN9 | bonus +100mb | zvládá doporučenou úroveň 9, +100 mb (nad rámec 400mb, do sloupec F, kam případně i NVP) |
| PSR1 | -20 | nezvládá ani základ PHP CodeSniffer (úroveň 1), což může znamenat, že obešli náš framework ipp-core |
| PSR12 | bonus +50mb | zvládá PHP CodeSniffer PSR-12, +50 mb (nad rámec 400mb, do sloupec F, kam případně i NVP) |
| Hodnocení dokumentace a objektové orientace (cca 150 mb) | | |
| STRUCT | -20 až -70 | chybí struktura nebo je nevhodná/nadpisy (stačí jediná úroveň) |
| SHORT | až -150 | moc krátké/nedostatečné; pokud student popsal vše potřebné, tak lze odpustit kratší rozsah |
| CH | á -10 (max. -50) | pravopisné chyby (vč. interpunkce) |
| FORMAT | většinou 0, ale až -50 | nedodrženy požadavky zadání a fóra (v případě, že obsahuje více než 2 stránky (nepočítejte do toho autorské-relevantní diagramy), tak označte oranžově) |
| MISSING | 0 mb | za text dokumentace zcela chybí (hodnotí se pouze komentáře 0-30mb, alespoň každá důležitá funkce by měla mít komentář k čemu je) |
| COPY | až -80 | text obsahuje úryvky ze zadání nebo cizí materiály (necitované obrázky z Internetu apod.) |
| STYLE | až -80 | stylizace vět, nečitelnost, nesrozumitelnost |
| FILO | až -50 | Zbyněk Křivka: lze využít i pro hodnocení zdrojových kódů chybí či nedostatečná filozofie návrhu skriptu (abstraktní popis struktury programu, co následuje za čím) |
| DOCTYPE | 0 až -30 | špatný typ souboru s dokumentací (vyžadujeme PDF nebo MarkDown, špatné jméno nepostihujeme) |
| TERM | á -10 až -20 | problematická terminologie (neobvyklá, nepřesná či přímo špatná), zaměřte se na správnou terminologii OOP (objekty, třídy, metody, instanční proměnné/atributy, dědičnost tříd, nikoli objektů apod.) |
| CONTENT | až -80 | nevhodný obsah (popis časového průběhu řešení, vyjadřování pocitů, irelevantních myšlenek a nepodložených názorů) |
| IR | až -40 | Nepopsaná vnitřní reprezentace (nebo je nedostatečná; např. je napsáno jen to, že "instrukce jsou ukládány do pole") |
| JAK | až -80 | technicky nedostatečný popis řešení (např. zda byly použity regulární výrazy/stavové řízení apod.) |
| NOOOP | až -100 | chybí snad použít objekty a objektově orientované paradigma, funkce jen zabaleny do jedné/dvou tříd (cca -50) |
| Hodnocení skriptu (cca 50 mb) | | |
| COMMENT | -20 až -50 | chybějící nebo nedostatečné komentáře ve zdrojovém textu (za všechny skripty dohromady) |
| NOOP | až -100 | chybí snad použít objekty a objektově orientované paradigma |
| SRCFORMAT | až -40 | opravdu velmi špatná štábní kultura zdrojového kódu (přehlednost, čitelnost kódu) |
| SPACETAB | bez postihu | Zbyněk Křivka: není nutné kontrolovat vždy, ale třeba jen namátkou kombinování mezer a tabelátorů k odsazování zdrojového textu (týká se především Pythonu) |
| DECOMPOSE | až -20 | skript není vůbec/dostatečně dekomponován na funkce (tolerujte velký switch ohledně výběru operačního kódu instrukce) |
| AUTHOR | bez postihu | ve skriptu chybí jméno autora |
| Hodnocení návrhu, UML diagram tříd a popis možností rozšíření (cca 100 mb) | | |
| NOSRP | až -50 | Ignorování nebo nešikovná aplikace principu jedné zodpovědnosti pro každou metodu |
| BADDP | až -50 | Naprosto nevhodné využití návrhového vzoru, nebo zcela špatná/chybějící implementace jinak dokumentovaného návrhového vzoru |
| EXT | -30 až -50 | nešikovný/nesmyslný nebo zcela chybějící popis rozšiřitelnosti vašeho návrhu |
| NOUML | až -100 | zcela chybějící UML diagram tříd |
| BADUML | až -80 | neodpovídající nebo syntakticky chybný UML diagram tříd |
| ^ | -30 | Prostý diagram tříd vygenerovaný v PhpStorm aj. neodpovídá úplně správně konvencím UML, navíc z něj nelze vyčíst bez dalších popisů nic jiného než schéma dědičnosti – nezaznemenává, jak spolu třídy interagují apod. |
| | -30 | chybí metody |
| | -10 | chybí AbstractInterpreter / výjimky rámce |
| | -30 | chybí nějaké třídy |
| | -10 | chybí jen nějaké výjimky |
| | -10 | třídy jsou nějak podivně shrnuté |
| | -15 | prázdné asociace |
| OWNDIF | až -10 | diagram nemá odlišeny vlastní třídy od knihovních dle požadavků zadání |
| BW | -5 | diagram s tmavým pozadím vložený do dokumentu se světlým pozadím |
| Upřesnění drobných chyb v dokumentaci | | |
| LANG | až -30 | míchání jazyků, anglické termíny v českém textu |
| HOV | až -40 | hovorové výrazy nebo nevhodné slangové výrazy |
| PRED | bez postihu | neslabičné předložky na konci řádku |
| FORM | až -30 | úprava, nekonzistentní velikost a typ písma apod. |
| BLOK | bez postihu | chybí zarovnaní do bloku místo méně pěkného zarovnání na prapor (doleva) |
| KAPTXT | bez postihu | mezi nadpisem a jeho podnadpisem by měl být vždy nějaký text |
| MDLINES | bez postihu | pro odřádkování v Markdown (v hlavičce dokumentace) je potřeba použít dvě mezery nebo zpětné lomítko |
| ICH | bez postihu | ich-forma (psaní v první osobě jednotného čísla) není většinou vhodná pro programovou dokumentaci |
| MEZ | bez postihu | za otevírající nebo před zavírající závorku mezera nepatří |
| SAZBA | bez postihu | alespoň identifikátory proměnných a funkcí se patří sázet písmem s jednotnou šířkou písmen (např. font Courier) |
| Zcela bez připomínek | | |
| OK | | OK=vše OK, dávejte jen u hodnocení, kde nechcete autora na nic upozornit, protože za nic neztratil body (aby nebyl komentář prázdný) |
| | | Kromě těchto zkratek můžete psát i jakýkoli další oficiální komentář, který se zobrazí studentovi. |
| | | Pokud chcete něco sdělit mě, tak použijte sloupec D a raději to nějak výrazně (červeně) podbarvěte. |
| | | U slovenštiny byste měli stejně jako u češtiny posoudit pravopis (tj. až -50mb). |
| | | Neodevzdaná dokumentace je automaticky 0 mb v částech Hodnocení dokumentace a Hodnocení návrhu. Pokud to uznáte za vhodné, lze udělit nějaké minibody za komentáře ve zdrojových kódech do výše cca 50mb. |
| Bonusy | | |
| EX | až +20 | Výjimky musí použít skoro povinně kvůli rámci ipp-core, ale pokud je nějak inovačně rozšíří (nestačí jen rozlišit podle kódů další podtřídy) |
| DP | až +40 | Obzvláště pěkné a zdokumentované (odůvodněné) použití návrhového vzoru (strop 400 mb zůstává) |
| SINGLETON | až -100 z NVP | Návrhový vzor Jedináček nebude v rámci NVP uznáván (viz zadání), takže je-li to jediný NV, tak nic. |
| NVPDOC | až -100 z NVP | Chybějící dokumentace rozšíření NVP (proč, kde, jak): (v případě, že to vypadá jako přidělávání práce - tj. uvedl NVP a není dokumentace, ani známky reálné implementace, tak strhávejte do záporu -50 i ze základu, což uveďte ve slovním hodnocení) |
| NVP: | popište detaily až +100 | Do sloupce F, bonusové body nad rámec 400 mb, když bude dobré popsáno a vhodné použití nějakého NV (nebo i více) |

200 za dokumentaci a kvalitu kódu (ca 150+50) |
100 za UML diagram |
