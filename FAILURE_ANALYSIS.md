# Failure Analysis Report - German ADDRESS Recognition

**Generated:** 1762964389.8507407
**Total Failures Analyzed:** 433
**Success Rate Context:** 91.3% (4,567/5,000 successful)

---

## Executive Summary

This document provides a comprehensive analysis of the 433 failed ADDRESS recognition cases from a 5,000-sample validation test. Failures have been systematically categorized to identify patterns and prioritize improvements.

### Failure Category Overview

| Category | Count | % of Failures | Description |
|----------|-------|---------------|-------------|
| incomplete_range | 269 | 62.1% | Number range partially detected (e.g., "44-46" → "44") |
| extra_preposition | 193 | 44.6% | Preposition incorrectly included in detection |
| missing_letter_suffix | 89 | 20.6% | House number letter suffix missing (e.g., "44a" → "44") |
| complete_miss | 48 | 11.1% | Address completely undetected |
| multi_hyphen_street | 24 | 5.5% | Street with multiple hyphens (e.g., "Bertha-von-Suttner-Str.") |
| miss_multi_hyphen_street | 23 | 5.3% | Multi-hyphen street completely missed |
| truncated_street_name | 22 | 5.1% | Street name partially captured |
| miss_letter_suffix | 13 | 3.0% | Address with letter suffix completely missed |
| other_mismatch | 4 | 0.9% | Miscellaneous detection mismatch |
| miss_hyphen_street | 2 | 0.5% | Hyphenated street completely missed |

---

## Category: Incomplete Range

**Count:** 269 failures (62.1% of all failures)

**Description:** Number range partially detected (e.g., "44-46" → "44")

### Representative Examples (showing up to 15 of 269)

**Example 1:**
- Expected: `Wiesenweg 51-57`
- Detected: `Wiesenweg 51`
- Sentence: *Wohnhaft Wiesenweg 51-57.*

**Example 2:**
- Expected: `Reitelshofen 62-68`
- Detected: `in der Reitelshofen 62`
- Sentence: *Treffen in der Reitelshofen 62-68 um 10 Uhr.*

**Example 3:**
- Expected: `Lilienweg 28-34`
- Detected: `in der Lilienweg 28`
- Sentence: *Treffen in der Lilienweg 28-34 um 10 Uhr.*

**Example 4:**
- Expected: `Am Schultenbusch 56-62`
- Detected: `Am Schultenbusch 56`
- Sentence: *Wohnhaft Am Schultenbusch 56-62.*

**Example 5:**
- Expected: `Martinsgasse 153-159`
- Detected: `in der Martinsgasse 153`
- Sentence: *Treffen in der Martinsgasse 153-159 um 10 Uhr.*

**Example 6:**
- Expected: `Im Kammerfeld 12-14`
- Detected: `in Im Kammerfeld 12`
- Sentence: *Wohnung in Im Kammerfeld 12-14*

**Example 7:**
- Expected: `Dorfstr. 129-133`
- Detected: `in der Dorfstr. 129`
- Sentence: *Treffen in der Dorfstr. 129-133 um 10 Uhr.*

**Example 8:**
- Expected: `Agirostr. 110-116`
- Detected: `in der Agirostr. 110`
- Sentence: *Treffen in der Agirostr. 110-116 um 10 Uhr.*

**Example 9:**
- Expected: `Giselastr. 76-82`
- Detected: `in der Giselastr. 76`
- Sentence: *Der Termin ist in der Giselastr. 76-82.*

**Example 10:**
- Expected: `Eschenhardt 106-110`
- Detected: `in Eschenhardt 106`
- Sentence: *Wohnung in Eschenhardt 106-110*

**Example 11:**
- Expected: `Abensberger Str. 184-190`
- Detected: `Abensberger Str. 184`
- Sentence: *Dokumentation für Abensberger Str. 184-190.*

**Example 12:**
- Expected: `Hinterm Garten 2-8`
- Detected: `an Hinterm Garten 2`
- Sentence: *Bitte an Hinterm Garten 2-8 schicken.*

**Example 13:**
- Expected: `Gartenstr. 84-88`
- Detected: `an Gartenstr. 84`
- Sentence: *Bitte an Gartenstr. 84-88 schicken.*

**Example 14:**
- Expected: `Bernhardsmühle 194-196`
- Detected: `in der Bernhardsmühle 194`
- Sentence: *Der Termin ist in der Bernhardsmühle 194-196.*

**Example 15:**
- Expected: `Jägerstr. 39-41`
- Detected: `in der Jägerstr. 39`
- Sentence: *Treffen in der Jägerstr. 39-41 um 10 Uhr.*

*...and 254 more cases in this category*

---

## Category: Extra Preposition

**Count:** 193 failures (44.6% of all failures)

**Description:** Preposition incorrectly included in detection

### Representative Examples (showing up to 15 of 193)

**Example 1:**
- Expected: `Reitelshofen 62-68`
- Detected: `in der Reitelshofen 62`
- Sentence: *Treffen in der Reitelshofen 62-68 um 10 Uhr.*

**Example 2:**
- Expected: `Lilienweg 28-34`
- Detected: `in der Lilienweg 28`
- Sentence: *Treffen in der Lilienweg 28-34 um 10 Uhr.*

**Example 3:**
- Expected: `Martinsgasse 153-159`
- Detected: `in der Martinsgasse 153`
- Sentence: *Treffen in der Martinsgasse 153-159 um 10 Uhr.*

**Example 4:**
- Expected: `Ladehofstr. 144g`
- Detected: `in Ladehofstr. 144`
- Sentence: *Wohnung in Ladehofstr. 144g*

**Example 5:**
- Expected: `Im Kammerfeld 12-14`
- Detected: `in Im Kammerfeld 12`
- Sentence: *Wohnung in Im Kammerfeld 12-14*

**Example 6:**
- Expected: `Dorfstr. 129-133`
- Detected: `in der Dorfstr. 129`
- Sentence: *Treffen in der Dorfstr. 129-133 um 10 Uhr.*

**Example 7:**
- Expected: `Agirostr. 110-116`
- Detected: `in der Agirostr. 110`
- Sentence: *Treffen in der Agirostr. 110-116 um 10 Uhr.*

**Example 8:**
- Expected: `Giselastr. 76-82`
- Detected: `in der Giselastr. 76`
- Sentence: *Der Termin ist in der Giselastr. 76-82.*

**Example 9:**
- Expected: `Eschenhardt 106-110`
- Detected: `in Eschenhardt 106`
- Sentence: *Wohnung in Eschenhardt 106-110*

**Example 10:**
- Expected: `Hinterm Garten 2-8`
- Detected: `an Hinterm Garten 2`
- Sentence: *Bitte an Hinterm Garten 2-8 schicken.*

**Example 11:**
- Expected: `Gartenstr. 84-88`
- Detected: `an Gartenstr. 84`
- Sentence: *Bitte an Gartenstr. 84-88 schicken.*

**Example 12:**
- Expected: `Bernhardsmühle 194-196`
- Detected: `in der Bernhardsmühle 194`
- Sentence: *Der Termin ist in der Bernhardsmühle 194-196.*

**Example 13:**
- Expected: `Splickgasse 150g`
- Detected: `in der Splickgasse 150`
- Sentence: *Der Termin ist in der Splickgasse 150g.*

**Example 14:**
- Expected: `Jägerstr. 39-41`
- Detected: `in der Jägerstr. 39`
- Sentence: *Treffen in der Jägerstr. 39-41 um 10 Uhr.*

**Example 15:**
- Expected: `Thränitzer Siedlung 79-85`
- Detected: `in der Thränitzer Siedlung 79`
- Sentence: *Der Termin ist in der Thränitzer Siedlung 79-85.*

*...and 178 more cases in this category*

---

## Category: Missing Letter Suffix

**Count:** 89 failures (20.6% of all failures)

**Description:** House number letter suffix missing (e.g., "44a" → "44")

### Representative Examples (showing up to 15 of 89)

**Example 1:**
- Expected: `Zum Hardenberger Schloß 188g`
- Detected: `Zum Hardenberger Schloß 188`
- Sentence: *Patient aus Zum Hardenberger Schloß 188g ist eingetroffen.*

**Example 2:**
- Expected: `Ladehofstr. 144g`
- Detected: `in Ladehofstr. 144`
- Sentence: *Wohnung in Ladehofstr. 144g*

**Example 3:**
- Expected: `Zum Heider Busch 28g`
- Detected: `Zum Heider Busch 28`
- Sentence: *Wohnhaft Zum Heider Busch 28g.*

**Example 4:**
- Expected: `Auf dem Hörtel 182g`
- Detected: `Auf dem Hörtel 182`
- Sentence: *Bitte an Auf dem Hörtel 182g schicken.*

**Example 5:**
- Expected: `Schönauer Ring 173g`
- Detected: `Schönauer Ring 173`
- Sentence: *Patient wohnt Schönauer Ring 173g.*

**Example 6:**
- Expected: `Splickgasse 150g`
- Detected: `in der Splickgasse 150`
- Sentence: *Der Termin ist in der Splickgasse 150g.*

**Example 7:**
- Expected: `Adelspfad 122g`
- Detected: `Adelspfad 122`
- Sentence: *Patient aus Adelspfad 122g ist eingetroffen.*

**Example 8:**
- Expected: `Jägerweg 22g`
- Detected: `Jägerweg 22`
- Sentence: *Dokumentation für Jägerweg 22g.*

**Example 9:**
- Expected: `Göllstr. 199g`
- Detected: `Göllstr. 199`
- Sentence: *Patient aus Göllstr. 199g ist eingetroffen.*

**Example 10:**
- Expected: `Kirchgasse 102g`
- Detected: `Kirchgasse 102`
- Sentence: *Patient aus Kirchgasse 102g ist eingetroffen.*

**Example 11:**
- Expected: `Starenweg 196g`
- Detected: `an Starenweg 196`
- Sentence: *Bitte an Starenweg 196g schicken.*

**Example 12:**
- Expected: `Hertinger Str. 31g`
- Detected: `Hertinger Str. 31`
- Sentence: *Dokumentation für Hertinger Str. 31g.*

**Example 13:**
- Expected: `Skulpturenpark 86g`
- Detected: `in der Skulpturenpark 86`
- Sentence: *Treffen in der Skulpturenpark 86g um 10 Uhr.*

**Example 14:**
- Expected: `Schenkenberger Weg 75g`
- Detected: `Schenkenberger Weg 75`
- Sentence: *Dokumentation für Schenkenberger Weg 75g.*

**Example 15:**
- Expected: `Richard-Wagner-Str. 126g`
- Detected: `Richard-Wagner-Str. 126`
- Sentence: *Dokumentation für Richard-Wagner-Str. 126g.*

*...and 74 more cases in this category*

---

## Category: Complete Miss

**Count:** 48 failures (11.1% of all failures)

**Description:** Address completely undetected

### Representative Examples (showing up to 15 of 48)

**Example 1:**
- Expected: `Bertha-von-Suttner-Str. 198c`
- Detected: `(nothing)`
- Sentence: *Dokumentation für Bertha-von-Suttner-Str. 198c.*

**Example 2:**
- Expected: `Franz-von-Kobell-Str. 134h`
- Detected: `(nothing)`
- Sentence: *Patient wohnt Franz-von-Kobell-Str. 134h.*

**Example 3:**
- Expected: `Hans-im-Glück-Weg 40`
- Detected: `(nothing)`
- Sentence: *Kontaktadresse: Hans-im-Glück-Weg 40, Hambühren*

**Example 4:**
- Expected: `X-2s 94`
- Detected: `(nothing)`
- Sentence: *Bitte an X-2s 94 schicken.*

**Example 5:**
- Expected: `Hinter dem Dorfe 49h`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Hinter dem Dorfe 49h.*

**Example 6:**
- Expected: `Anna-von-Russegg-Weg 24c`
- Detected: `(nothing)`
- Sentence: *Dokumentation für Anna-von-Russegg-Weg 24c.*

**Example 7:**
- Expected: `von-Wenkheim-Str. 54`
- Detected: `(nothing)`
- Sentence: *Patient wohnt von-Wenkheim-Str. 54.*

**Example 8:**
- Expected: `Werner-von-Siemens-Str. 3-7`
- Detected: `(nothing)`
- Sentence: *Patient aus Werner-von-Siemens-Str. 3-7 ist eingetroffen.*

**Example 9:**
- Expected: `Walter-von-Molo-Weg 193f`
- Detected: `(nothing)`
- Sentence: *Patient aus Walter-von-Molo-Weg 193f ist eingetroffen.*

**Example 10:**
- Expected: `Str. des Aufbaus 112`
- Detected: `(nothing)`
- Sentence: *Treffen in der Str. des Aufbaus 112 um 10 Uhr.*

**Example 11:**
- Expected: `Graf-von-Zeppelin-Str. 161d`
- Detected: `(nothing)`
- Sentence: *Wohnhaft Graf-von-Zeppelin-Str. 161d.*

**Example 12:**
- Expected: `Peter-und-Paul-Str. 10`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Peter-und-Paul-Str. 10.*

**Example 13:**
- Expected: `Park des Rittergut Rosenthal 4h`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Park des Rittergut Rosenthal 4h.*

**Example 14:**
- Expected: `Von-der-Recke-Str. 128`
- Detected: `(nothing)`
- Sentence: *Treffen in der Von-der-Recke-Str. 128 um 10 Uhr.*

**Example 15:**
- Expected: `Unter'm Kurhut 93`
- Detected: `(nothing)`
- Sentence: *Bitte an Unter'm Kurhut 93 schicken.*

*...and 33 more cases in this category*

---

## Category: Multi Hyphen Street

**Count:** 24 failures (5.5% of all failures)

**Description:** Street with multiple hyphens (e.g., "Bertha-von-Suttner-Str.")

### Representative Examples (showing up to 15 of 24)

**Example 1:**
- Expected: `Eduard-Röders-Str. 45-47`
- Detected: `Eduard-Röders-Str. 45`
- Sentence: *Wohnhaft Eduard-Röders-Str. 45-47.*

**Example 2:**
- Expected: `Richard-Wagner-Str. 126g`
- Detected: `Richard-Wagner-Str. 126`
- Sentence: *Dokumentation für Richard-Wagner-Str. 126g.*

**Example 3:**
- Expected: `St.-Brevin-Ring 82-86`
- Detected: `St.-Brevin-Ring 82`
- Sentence: *Wohnhaft St.-Brevin-Ring 82-86.*

**Example 4:**
- Expected: `August-Lüdenbach-Str. 197-201`
- Detected: `in der August-Lüdenbach-Str. 197`
- Sentence: *Treffen in der August-Lüdenbach-Str. 197-201 um 10 Uhr.*

**Example 5:**
- Expected: `Glück-Auf-Str. 186-188`
- Detected: `Glück-Auf-Str. 186`
- Sentence: *Dokumentation für Glück-Auf-Str. 186-188.*

**Example 6:**
- Expected: `Monica-Lochner-Fischer-Str. 55-59`
- Detected: `in der Monica-Lochner-Fischer-Str. 55`
- Sentence: *Der Termin ist in der Monica-Lochner-Fischer-Str. 55-59.*

**Example 7:**
- Expected: `Albrecht-Dürer-Str. 8-10`
- Detected: `in der Albrecht-Dürer-Str. 8`
- Sentence: *Treffen in der Albrecht-Dürer-Str. 8-10 um 10 Uhr.*

**Example 8:**
- Expected: `Adolph-Kolping-Str. 56-60`
- Detected: `an Adolph-Kolping-Str. 56`
- Sentence: *Bitte an Adolph-Kolping-Str. 56-60 schicken.*

**Example 9:**
- Expected: `Paul-Gerhardt-Str. 84-90`
- Detected: `in Paul-Gerhardt-Str. 84`
- Sentence: *Wohnung in Paul-Gerhardt-Str. 84-90*

**Example 10:**
- Expected: `Gottlob-Grotz-Str. 114-120`
- Detected: `Gottlob-Grotz-Str. 114`
- Sentence: *Wohnhaft Gottlob-Grotz-Str. 114-120.*

**Example 11:**
- Expected: `Budakezi-Piliscsaba-Weg 10-14`
- Detected: `in der Budakezi-Piliscsaba-Weg 10`
- Sentence: *Der Termin ist in der Budakezi-Piliscsaba-Weg 10-14.*

**Example 12:**
- Expected: `Wilhelm-Henze-Weg 145-149`
- Detected: `in Wilhelm-Henze-Weg 145`
- Sentence: *Wohnung in Wilhelm-Henze-Weg 145-149*

**Example 13:**
- Expected: `Von-Burgdorf-Str. 200g`
- Detected: `in der Von-Burgdorf-Str. 200`
- Sentence: *Treffen in der Von-Burgdorf-Str. 200g um 10 Uhr.*

**Example 14:**
- Expected: `Alfriede-Marioth-Str. 190g`
- Detected: `in der Alfriede-Marioth-Str. 190`
- Sentence: *Treffen in der Alfriede-Marioth-Str. 190g um 10 Uhr.*

**Example 15:**
- Expected: `Peter-Wahl-Weg 54-56`
- Detected: `in der Peter-Wahl-Weg 54`
- Sentence: *Der Termin ist in der Peter-Wahl-Weg 54-56.*

*...and 9 more cases in this category*

---

## Category: Miss Multi Hyphen Street

**Count:** 23 failures (5.3% of all failures)

**Description:** Multi-hyphen street completely missed

### Representative Examples (showing up to 15 of 23)

**Example 1:**
- Expected: `Bertha-von-Suttner-Str. 198c`
- Detected: `(nothing)`
- Sentence: *Dokumentation für Bertha-von-Suttner-Str. 198c.*

**Example 2:**
- Expected: `Franz-von-Kobell-Str. 134h`
- Detected: `(nothing)`
- Sentence: *Patient wohnt Franz-von-Kobell-Str. 134h.*

**Example 3:**
- Expected: `Hans-im-Glück-Weg 40`
- Detected: `(nothing)`
- Sentence: *Kontaktadresse: Hans-im-Glück-Weg 40, Hambühren*

**Example 4:**
- Expected: `Anna-von-Russegg-Weg 24c`
- Detected: `(nothing)`
- Sentence: *Dokumentation für Anna-von-Russegg-Weg 24c.*

**Example 5:**
- Expected: `von-Wenkheim-Str. 54`
- Detected: `(nothing)`
- Sentence: *Patient wohnt von-Wenkheim-Str. 54.*

**Example 6:**
- Expected: `Werner-von-Siemens-Str. 3-7`
- Detected: `(nothing)`
- Sentence: *Patient aus Werner-von-Siemens-Str. 3-7 ist eingetroffen.*

**Example 7:**
- Expected: `Walter-von-Molo-Weg 193f`
- Detected: `(nothing)`
- Sentence: *Patient aus Walter-von-Molo-Weg 193f ist eingetroffen.*

**Example 8:**
- Expected: `Graf-von-Zeppelin-Str. 161d`
- Detected: `(nothing)`
- Sentence: *Wohnhaft Graf-von-Zeppelin-Str. 161d.*

**Example 9:**
- Expected: `Peter-und-Paul-Str. 10`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Peter-und-Paul-Str. 10.*

**Example 10:**
- Expected: `Von-der-Recke-Str. 128`
- Detected: `(nothing)`
- Sentence: *Treffen in der Von-der-Recke-Str. 128 um 10 Uhr.*

**Example 11:**
- Expected: `Carl-von-Ossietzky-Weg 95`
- Detected: `(nothing)`
- Sentence: *Adresse: Carl-von-Ossietzky-Weg 95*

**Example 12:**
- Expected: `Von-der-Leyen-Str. 24-28`
- Detected: `(nothing)`
- Sentence: *Wohnhaft Von-der-Leyen-Str. 24-28.*

**Example 13:**
- Expected: `Wolter-von-Plettenberg-Str. 186`
- Detected: `(nothing)`
- Sentence: *Wohnung in Wolter-von-Plettenberg-Str. 186*

**Example 14:**
- Expected: `Freiherr-vom-Stein-Weg 185`
- Detected: `(nothing)`
- Sentence: *Patient wohnt Freiherr-vom-Stein-Weg 185.*

**Example 15:**
- Expected: `Johann-Wolfgang-von-Goethe-Str. 198`
- Detected: `(nothing)`
- Sentence: *Patient wohnt Johann-Wolfgang-von-Goethe-Str. 198.*

*...and 8 more cases in this category*

---

## Category: Truncated Street Name

**Count:** 22 failures (5.1% of all failures)

**Description:** Street name partially captured

### Representative Examples (showing up to 15 of 22)

**Example 1:**
- Expected: `In de Wisch 185b`
- Detected: `Wisch 185b.`
- Sentence: *Wohnhaft In de Wisch 185b.*

**Example 2:**
- Expected: `Weiler an der Eck 128d`
- Detected: `an der Eck 128d`
- Sentence: *Kontaktadresse: Weiler an der Eck 128d, Stödtlen*

**Example 3:**
- Expected: `südlicher Serviceweg am Mittellandkanal 150`
- Detected: `am Mittellandkanal 150.`
- Sentence: *Dokumentation für südlicher Serviceweg am Mittellandkanal 150.*

**Example 4:**
- Expected: `Am alten Gutshof 177`
- Detected: `Gutshof 177`
- Sentence: *Treffen in der Am alten Gutshof 177 um 10 Uhr.*

**Example 5:**
- Expected: `Park im Eichenhof 117`
- Detected: `Eichenhof 117`
- Sentence: *Bitte an Park im Eichenhof 117 schicken.*

**Example 6:**
- Expected: `Im langen Rain 47b`
- Detected: `Rain 47b.`
- Sentence: *Wohnhaft Im langen Rain 47b.*

**Example 7:**
- Expected: `Am alten Sportplatz 47`
- Detected: `Sportplatz 47`
- Sentence: *Treffen in der Am alten Sportplatz 47 um 10 Uhr.*

**Example 8:**
- Expected: `Am alten Hafen 185a`
- Detected: `Hafen 185a.`
- Sentence: *Patient wohnt Am alten Hafen 185a.*

**Example 9:**
- Expected: `SBV Senioren Wohnpark 138`
- Detected: `Wohnpark 138.`
- Sentence: *Wohnhaft SBV Senioren Wohnpark 138.*

**Example 10:**
- Expected: `Allee an den Birken 62`
- Detected: `an den Birken 62`
- Sentence: *Wohnung in Allee an den Birken 62*

**Example 11:**
- Expected: `An der alten Schmiede 112-118`
- Detected: `Schmiede 112-118`
- Sentence: *Treffen in der An der alten Schmiede 112-118 um 10 Uhr.*

**Example 12:**
- Expected: `III. Rheinstr. 176`
- Detected: `Rheinstr. 176.`
- Sentence: *Wohnhaft III. Rheinstr. 176.*

**Example 13:**
- Expected: `Boos von Waldeckhof 144`
- Detected: `Waldeckhof 144`
- Sentence: *Treffen in der Boos von Waldeckhof 144 um 10 Uhr.*

**Example 14:**
- Expected: `Am alten Bahnhof 175`
- Detected: `Bahnhof 175,`
- Sentence: *Kontaktadresse: Am alten Bahnhof 175, Bobritzsch-Hilbersdorf*

**Example 15:**
- Expected: `An der alten Fähre 18`
- Detected: `Fähre 18`
- Sentence: *Bitte an An der alten Fähre 18 schicken.*

*...and 7 more cases in this category*

---

## Category: Miss Letter Suffix

**Count:** 13 failures (3.0% of all failures)

**Description:** Address with letter suffix completely missed

### Representative Examples (showing up to 15 of 13)

**Example 1:**
- Expected: `Bertha-von-Suttner-Str. 198c`
- Detected: `(nothing)`
- Sentence: *Dokumentation für Bertha-von-Suttner-Str. 198c.*

**Example 2:**
- Expected: `Franz-von-Kobell-Str. 134h`
- Detected: `(nothing)`
- Sentence: *Patient wohnt Franz-von-Kobell-Str. 134h.*

**Example 3:**
- Expected: `X-2s 94`
- Detected: `(nothing)`
- Sentence: *Bitte an X-2s 94 schicken.*

**Example 4:**
- Expected: `Hinter dem Dorfe 49h`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Hinter dem Dorfe 49h.*

**Example 5:**
- Expected: `Anna-von-Russegg-Weg 24c`
- Detected: `(nothing)`
- Sentence: *Dokumentation für Anna-von-Russegg-Weg 24c.*

**Example 6:**
- Expected: `Walter-von-Molo-Weg 193f`
- Detected: `(nothing)`
- Sentence: *Patient aus Walter-von-Molo-Weg 193f ist eingetroffen.*

**Example 7:**
- Expected: `Graf-von-Zeppelin-Str. 161d`
- Detected: `(nothing)`
- Sentence: *Wohnhaft Graf-von-Zeppelin-Str. 161d.*

**Example 8:**
- Expected: `Park des Rittergut Rosenthal 4h`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Park des Rittergut Rosenthal 4h.*

**Example 9:**
- Expected: `Frei im Felde 131b`
- Detected: `(nothing)`
- Sentence: *Treffen in der Frei im Felde 131b um 10 Uhr.*

**Example 10:**
- Expected: `Str. der Deutschen Einheit 131h`
- Detected: `(nothing)`
- Sentence: *Bitte an Str. der Deutschen Einheit 131h schicken.*

**Example 11:**
- Expected: `'s Untere Wegle 132f`
- Detected: `(nothing)`
- Sentence: *Bitte an 's Untere Wegle 132f schicken.*

**Example 12:**
- Expected: `Str. der Jugend 16d`
- Detected: `(nothing)`
- Sentence: *Der Termin ist in der Str. der Jugend 16d.*

**Example 13:**
- Expected: `Immanuel-von-Ketteler-Weg 101f`
- Detected: `(nothing)`
- Sentence: *Kontaktadresse: Immanuel-von-Ketteler-Weg 101f, Frechen*

---

## Category: Other Mismatch

**Count:** 4 failures (0.9% of all failures)

**Description:** Miscellaneous detection mismatch

### Representative Examples (showing up to 15 of 4)

**Example 1:**
- Expected: `Weg 314 133`
- Detected: `Weg 314`
- Sentence: *Patient wohnt Weg 314 133.*

**Example 2:**
- Expected: `ZG Berliner Allee 184b`
- Detected: `Berliner Allee 184b.`
- Sentence: *Dokumentation für ZG Berliner Allee 184b.*

**Example 3:**
- Expected: `Weg 85 57`
- Detected: `Weg 85`
- Sentence: *Patient wohnt Weg 85 57.*

**Example 4:**
- Expected: `Str. 150 136`
- Detected: `Str. 150`
- Sentence: *Patient wohnt Str. 150 136.*

---

## Category: Miss Hyphen Street

**Count:** 2 failures (0.5% of all failures)

**Description:** Hyphenated street completely missed

### Representative Examples (showing up to 15 of 2)

**Example 1:**
- Expected: `X-2s 94`
- Detected: `(nothing)`
- Sentence: *Bitte an X-2s 94 schicken.*

**Example 2:**
- Expected: `Vor den Toren von Griesheim 95-97`
- Detected: `(nothing)`
- Sentence: *Bitte an Vor den Toren von Griesheim 95-97 schicken.*

---

## Recommendations for Improvement

Based on the failure analysis, here are prioritized recommendations:

| Priority | Impact | Issue | Description | Cases Affected | Estimated Effort |
|----------|--------|-------|-------------|----------------|------------------|
| 1 | **HIGH** | Number Range Extension | Fix `_extend_number_range()` function to properly capture full ranges (e.g., "44-46", "12-14") | 269 cases (62.1%) | MEDIUM - Requires debugging tokenization and boundary detection |
| 2 | **HIGH** | Letter Suffix Capture | Improve detection of single letter suffixes after house numbers (e.g., "44a", "107g") | 102 cases (23.6%) | MEDIUM - Requires refining boundary detection in `_extend_number_range()` |
| 3 | **MEDIUM** | Multi-Hyphen Street Names | Enhance pattern matching for complex hyphenated streets (e.g., "Bertha-von-Suttner-Str.", "Von-der-Leyen-Straße") | 47 cases (10.9%) | HIGH - May require new EntityRuler patterns or gazetteer normalization improvements |
| 4 | **MEDIUM** | Complete Detection Failures | Investigate addresses that are entirely undetected - may indicate pattern gaps or gazetteer mismatches | 48 cases (11.1%) | VARIES - Requires case-by-case analysis |

### Estimated Impact of Fixes

Based on the categorization:
- **Quick wins** (Range + Letter suffix fixes): 371 cases = **+7.4pp** potential improvement
- **Current accuracy:** 91.3%
- **Target with quick wins:** ~98.7%
- **Theoretical maximum** (all categories fixed): ~100.0%

**Note:** Some failures may have multiple root causes, so actual improvement may vary.
