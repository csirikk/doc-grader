# Rubric codes

## IPP

| Code      | Deduction/Bonus range                          | Notes                                                                                                                       |
|-----------|------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| AUTHOR    | bez postihu                                    | ve skriptu chybí jméno autora                                                                                               |
| BADDP     | až -50                                         | Naprosto nevhodné využití návrhového vzoru, nebo zcela špatná/chybějící implementace jinak dokumentovaného návrhového vzoru |
| BADUML    | až -80                                         | neodpovídající nebo syntakticky chybný UML diagram tříd, prostý diagram z IDE; chybí metody/třídy/výjimky; prázdné asociace |
| BLOK      | bez postihu                                    | chybí zarovnaní do bloku místo méně pěkného zarovnání na prapor (doleva); (jen pro PDF v druhé tabulce)                     |
| BW        | -5                                             | diagram s tmavým pozadím vložený do dokumentu se světlým pozadím                                                            |
| CH        | -10 (max. -50);   -5 (max. -30)                | pravopisné chyby (vč. interpunkce)                                                                                          |
| COMMENT   | -10 až -30; -20 až -50                         | chybějící nebo nedostatečné komentáře; (u malé verze: za všechny skripty dohromady)                                         |
| CONTENT   | až -40; až -80                                 | nevhodný obsah (časový průběh řešení, pocity, irelevantní myšlenky, nepodložené názory)                                     |
| COPY      | až -50; až -80                                 | text obsahuje úryvky ze zadání nebo cizí materiály (necitované obrázky apod.)                                               |
| DECOMPOSE | až -20                                         | skript není vůbec/dostatečně dekomponován na funkce; tolerujte velký switch                                                 |
| DOCTYPE   | 0 až -20; 0 až -30                             | špatný typ souboru s dokumentací (vyžadujeme PDF nebo Markdown; jméno nepostihujeme)                                        |
| DP        | až +40                                         | obzvlášť pěkné a zdokumentované použití návrhového vzoru (strop zůstává)                                                    |
| EX        | až +20                                         | inovační rozšíření výjimek (u malé verze také bonus)                                                                        |
| EXT       | -30 až -50                                     | nešikovný/nesmyslný či chybějící popis rozšiřitelnosti návrhu                                                               |
| FILO      | až -50                                         | nedostatečná filozofie návrhu skriptu                                                                                       |
| FORM      | až -10; až -30                                 | úprava, nekonzistentní velikost/typ písma                                                                                   |
| FORMAT    | většinou 0, ale až -20; většinou 0, ale až -50 | nedodrženy požadavky zadání/fóra; u více než 2 stran označit oranžově                                                       |
| HOV       | až -20; až -40                                 | hovorové/slangové výrazy (u malé verze „parsování“ tolerováno)                                                              |
| ICH       | bez postihu                                    | ich-forma není většinou vhodná                                                                                              |
| IR        | až -20; až -40                                 | nepopsaná/dostatečná vnitřní reprezentace (např. jen „instrukce do pole“ / „přiřazení do AST“)                              |
| JAK       | až -50; až -80                                 | technicky nedostatečný popis řešení (např. regexy/stavový automat, parser-generator…)                                       |
| KAPTXT    | bez postihu                                    | mezi nadpisem a podnadpisem má být text                                                                                     |
| LANG      | až -20; až -30                                 | míchání jazyků, anglické termíny v českém textu                                                                             |
| MDLINES   | bez postihu                                    | v Markdownu je na odřádkování třeba 2 mezery nebo zpětné lomítko                                                            |
| MEZ       | bez postihu                                    | mezery okolo závorek/na konci řádku                                                                                         |
| MISSING   | 0 mb za text                                   | dokumentace zcela chybí (hodnotí se jen komentáře 0–30 mb; u malé verze i poznámka k frameworku)                            |
| NOOOP     | až -100                                        | chybí (rozumné) použití OOP; funkce jen zabaleny do 1–2 tříd (cca -50)                                                      |
| NOOP      | až -100                                        | chybí (rozumné) použití OOP                                                                                                 |
| NOSRP     | až -50                                         | ignorování/špatná aplikace Single Responsibility                                                                            |
| NOUML     | až -100                                        | zcela chybějící UML diagram tříd                                                                                            |
| NVP       | až +100                                        | bonus nad rámec 400 mb za dobře popsané a vhodné NV (sloupec F)                                                             |
| NVPDOC    | až -100 z NVP                                  | chybějící dokumentace rozšíření NVP; při „přidělávání práce“ strhnout i -50 ze základu                                      |
| OK        | -                                              | použijte jen tam, kde nechcete autora na nic upozornit (bez ztrát)                                                          |
| OOP       | až +20                                         | pěkné použití OOP ve skriptech i správná terminologie                                                                       |
| OWNDIF    | až -10                                         | v UML nerozlišeny vlastní třídy vs. knihovní                                                                                |
| PRED      | bez postihu                                    | neslabičné předložky na konci řádku                                                                                         |
| PSR1      | -20                                            | nezvládá základ PHP CodeSniffer (úroveň 1)                                                                                  |
| PSR12     | bonus +50mb                                    | zvládá PSR-12 (+50 mb; nad rámec 400 mb)                                                                                    |
| SAZBA     | bez postihu                                    | identifikátory sázet písmem s jednotnou šířkou (Courier ap.)                                                                |
| SHORT     | až -150; až -70                                | moc krátké/nedostatečné; lze odpustit pokud je vše podstatné                                                                |
| SINGLETON | až -100 z NVP                                  | „Jedináček“ v NVP se neuznává; je-li jediný NV, tak nic                                                                     |
| SPACETAB  | bez postihu                                    | kombinování mezer a tabů - jen namátkově, netřeba vždy kontrolovat                                                          |
| SRCFORMAT | až -20; až -40                                 | velmi špatná „štábní kultura“ zdrojáků                                                                                      |
| STRUCT    | -10 až -30; -20 až -70                         | chybí/nevhodná struktura, nadpisy                                                                                           |
| STYLE     | až -40; až -80                                 | stylizace vět; nečitelnost, nesrozumitelnost                                                                                |
| TERM      | á -10 až -20; á -5 až -10                      | problematická terminologie (zaměřit se na správnou OOP terminologii…)                                                       |

                                                       |

## IFJ

| Code      | Deduction/Bonus range | Notes                                                           |
|-----------|-----------------------|-----------------------------------------------------------------|
| 1. strana | -                     | chybějící informace na 1. straně dokumentace                    |
| BLOK      | -                     | text není zarovnán do bloku                                     |
| GK        | -                     | chybějící/nedostatečný popis generování kódu                    |
| HOV       | -                     | hovorové výrazy; zbytečné anglicismy                            |
| KA        | -                     | chyby v KA; nedeterminismus; chybějící lexémy (např. komentáře) |
| KAPTXT    | -                     | více nadpisů hned za sebou                                      |
| LANG      | -                     | míchání jazyků (čeština/slovenština)                            |
| LL        | -                     | chyby/nedostatky v LL tabulce                                   |
| LLT       | -                     | chybějící/chybná LL tabulka (FOLLOW + ε pravidla ap.)           |
| MEZ       | -                     | špatné psaní mezer (okolo závorek/interpunkce)                  |
| PSA       | -                     | chybějící/nedostatečný popis precedenční analýzy                |
| PT        | -                     | chybějící/chybná/nečitelná precedenční tabulka                  |
| RP        | -                     | chybí popis rozdělení práce                                     |
| SA        | -                     | nedostatečný/nesprávný popis syntaktické analýzy                |
| SAV       | -                     | nedostatečný popis syntaktické analýzy výrazů                   |
| SAZBA     | -                     | identifikátory sázet písmem s jednotnou šířkou                  |
| SHORT     | -                     | nedostatečný, nekonkrétní popis řešení                          |
| STYLE     | -                     | nesrozumitelné věty, dlouhá složitá souvětí                     |
| SéA       | -                     | chybí/nedostatečný popis sémantické analýzy                     |
| TS        | -                     | chybějící/nedostatečný popis tabulky symbolů/implementace       |
| gram.     | -                     | gramatické chyby                                                |
| strukt.   | -                     | nedostatky ve struktuře (např. chybí závěr)                     |
| term.     | -                     | nepřesná terminologie                                           |
| typ.      | -                     | typografické nedostatky (např. nezarovnáno do bloku)            |
