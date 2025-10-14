# Rubric codes

## IPP

| Code      | Deduction/Bonus range                          | Notes                                                                                                                       |
|-----------|------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| SHORT     | až -150; až -70                                | moc krátké/nedostatečné; lze odpustit pokud je vše podstatné                                                                |
| NOOOP     | až -100                                        | chybí (rozumné) použití OOP; funkce jen zabaleny do 1–2 tříd (cca -50)                                                      |
| NOOP      | až -100                                        | chybí (rozumné) použití OOP                                                                                                 |
| NOUML     | až -100                                        | zcela chybějící UML diagram tříd                                                                                            |
| NVPDOC    | až -100 z NVP                                  | chybějící dokumentace rozšíření NVP; při „přidělávání práce“ strhnout i -50 ze základu                                      |
| SINGLETON | až -100 z NVP                                  | „Jedináček“ v NVP se neuznává; je-li jediný NV, tak nic                                                                     |
| NVP       | až +100                                        | bonus nad rámec 400 mb za dobře popsané a vhodné NV (sloupec F)                                                             |
| BADUML    | až -80                                         | neodpovídající nebo syntakticky chybný UML diagram tříd, prostý diagram z IDE; chybí metody/třídy/výjimky; prázdné asociace |
| JAK       | až -50; až -80                                 | technicky nedostatečný popis řešení (např. regexy/stavový automat, parser-generator…)                                       |
| STYLE     | až -40; až -80                                 | stylizace vět; nečitelnost, nesrozumitelnost                                                                                |
| CONTENT   | až -40; až -80                                 | nevhodný obsah (časový průběh řešení, pocity, irelevantní myšlenky, nepodložené názory)                                     |
| COPY      | až -50; až -80                                 | text obsahuje úryvky ze zadání nebo cizí materiály (necitované obrázky apod.)                                               |
| STRUCT    | -10 až -30; -20 až -70                         | chybí/nevhodná struktura, nadpisy                                                                                           |
| COMMENT   | -10 až -30; -20 až -50                         | chybějící nebo nedostatečné komentáře; (u malé verze: za všechny skripty dohromady)                                         |
| BADDP     | až -50                                         | Naprosto nevhodné využití návrhového vzoru, nebo zcela špatná/chybějící implementace jinak dokumentovaného návrhového vzoru |
| FILO      | až -50                                         | nedostatečná filozofie návrhu skriptu                                                                                       |
| NOSRP     | až -50                                         | ignorování/špatná aplikace Single Responsibility                                                                            |
| EXT       | -30 až -50                                     | nešikovný/nesmyslný či chybějící popis rozšiřitelnosti návrhu                                                               |
| FORMAT    | většinou 0, ale až -20; většinou 0, ale až -50 | nedodrženy požadavky zadání/fóra; u více než 2 stran označit oranžově                                                       |
| CH        | -10 (max. -50);   -5 (max. -30)                | pravopisné chyby (vč. interpunkce)                                                                                          |
| PSR12     | bonus +50mb                                    | zvládá PSR-12 (+50 mb; nad rámec 400 mb)                                                                                    |
| DP        | až +40                                         | obzvlášť pěkné a zdokumentované použití návrhového vzoru (strop zůstává)                                                    |
| IR        | až -20; až -40                                 | nepopsaná/dostatečná vnitřní reprezentace (např. jen „instrukce do pole“ / „přiřazení do AST”)                              |
| SRCFORMAT | až -20; až -40                                 | velmi špatná „štábní kultura“ zdrojáků                                                                                      |
| HOV       | až -20; až -40                                 | hovorové/slangové výrazy (u malé verze „parsování“ tolerováno)                                                              |
| FORM      | až -10; až -30                                 | úprava, nekonzistentní velikost/typ písma                                                                                   |
| LANG      | až -20; až -30                                 | míchání jazyků, anglické termíny v českém textu                                                                             |
| DOCTYPE   | 0 až -20; 0 až -30                             | špatný typ souboru s dokumentací (vyžadujeme PDF nebo Markdown; jméno nepostihujeme)                                        |
| DECOMPOSE | až -20                                         | skript není vůbec/dostatečně dekomponován na funkce; tolerujte velký switch                                                 |
| PSR1      | -20                                            | nezvládá základ PHP CodeSniffer (úroveň 1)                                                                                  |
| TERM      | á -10 až -20; á -5 až -10                      | problematická terminologie (zaměřit se na správnou OOP terminologii…)                                                       |
| OOP       | až +20                                         | pěkné použití OOP ve skriptech i správná terminologie                                                                       |
| EX        | až +20                                         | inovační rozšíření výjimek (u malé verze také bonus)                                                                        |
| OWNDIF    | až -10                                         | v UML nerozlišeny vlastní třídy vs. knihovní                                                                                |
| BW        | -5                                             | diagram s tmavým pozadím vložený do dokumentu se světlým pozadím                                                            |
| MISSING   | 0 mb za text                                   | dokumentace zcela chybí (hodnotí se jen komentáře 0–30 mb; u malé verze i poznámka k frameworku)                            |
| AUTHOR    | bez postihu                                    | ve skriptu chybí jméno autora                                                                                               |
| BLOK      | bez postihu                                    | chybí zarovnaní do bloku místo méně pěkného zarovnání na prapor (doleva); (jen pro PDF v druhé tabulce)                     |
| ICH       | bez postihu                                    | ich-forma není většinou vhodná                                                                                              |
| KAPTXT    | bez postihu                                    | mezi nadpisem a podnadpisem má být text                                                                                     |
| MDLINES   | bez postihu                                    | v Markdownu je na odřádkování třeba 2 mezery nebo zpětné lomítko                                                            |
| MEZ       | bez postihu                                    | mezery okolo závorek/na konci řádku                                                                                         |
| OK        | -                                              | použijte jen tam, kde nechcete autora na nic upozornit (bez ztrát)                                                          |
| PRED      | bez postihu                                    | neslabičné předložky na konci řádku                                                                                         |
| SAZBA     | bez postihu                                    | identifikátory sázet písmem s jednotnou šířkou (Courier ap.)                                                                |
| SPACETAB  | bez postihu                                    | kombinování mezer a tabů - jen namátkově, netřeba vždy kontrolovat                                                          |

                                                       |

## IFJ

| Code      | Deduction/Bonus range | Notes                                                           |
|-----------|-----------------------|-----------------------------------------------------------------|
| SHORT     | -                     | nedostatečný, nekonkrétní popis řešení                          |
| LLT       | -                     | chybějící/chybná LL tabulka (FOLLOW + ε pravidla ap.)           |
| PT        | -                     | chybějící/chybná/nečitelná precedenční tabulka                  |
| KA        | -                     | chyby v KA; nedeterminismus; chybějící lexémy (např. komentáře) |
| LL        | -                     | chyby/nedostatky v LL tabulce                                   |
| PSA       | -                     | chybějící/nedostatečný popis precedenční analýzy                |
| SA        | -                     | nedostatečný/nesprávný popis syntaktické analýzy                |
| SAV       | -                     | nedostatečný popis syntaktické analýzy výrazů                   |
| SéA       | -                     | chybí/nedostatečný popis sémantické analýzy                     |
| TS        | -                     | chybějící/nedostatečný popis tabulky symbolů/implementace       |
| GK        | -                     | chybějící/nedostatečný popis generování kódu                    |
| RP        | -                     | chybí popis rozdělení práce                                     |
| STYLE     | -                     | nesrozumitelné věty, dlouhá složitá souvětí                     |
| gram.     | -                     | gramatické chyby                                                |
| term.     | -                     | nepřesná terminologie                                           |
| strukt.   | -                     | nedostatky ve struktuře (např. chybí závěr)                     |
| LANG      | -                     | míchání jazyků (čeština/slovenština)                            |
| HOV       | -                     | hovorové výrazy; zbytečné anglicismy                            |
| 1. strana | -                     | chybějící informace na 1. straně dokumentace                    |
| SAZBA     | -                     | identifikátory sázet písmem s jednotnou šířkou                  |
| MEZ       | -                     | špatné psaní mezer (okolo závorek/interpunkce)                  |
| typ.      | -                     | typografické nedostatky (např. nezarovnáno do bloku)            |
| BLOK      | -                     | text není zarovnán do bloku                                     |
| KAPTXT    | -                     | více nadpisů hned za sebou                                      |
