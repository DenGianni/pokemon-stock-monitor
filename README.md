# Pokémon Stock Monitor — GitHub Actions

Continue Pokémon TCG voorraadmonitor voor **Bol.com België** en **MediaMarkt België**.
De monitor zoekt naar Engelstalige Pokémon TCG-producten en stuurt Discord-meldingen bij nieuwe voorraad/restocks.

## Belangrijk
Gebruik een **publieke GitHub-repository** als je de GitHub-hosted runner gratis en zonder maandelijkse Actions-minuten wilt gebruiken. GitHub geeft voor publieke repositories gratis gebruik van standaard runners. Geplande workflows kunnen maximaal iedere 5 minuten worden gepland.

## Installatie

1. Maak op GitHub een **nieuwe publieke repository**, bijvoorbeeld `pokemon-stock-monitor`.
2. Upload de inhoud van deze map naar de repository. Zorg dat `.github/workflows/pokemon-stock.yml` exact op die plaats staat.
3. Ga in de repository naar **Settings → Secrets and variables → Actions**.
4. Kies **New repository secret**.
5. Naam: `DISCORD_WEBHOOK`
6. Waarde: je **nieuwe** Discord webhook URL.
7. Ga naar **Actions** en kies **Pokémon Stock Monitor**.
8. Kies **Run workflow** voor een eerste handmatige test.
9. Bekijk de workflow-log. Bij een eerste run wordt de huidige voorraad als beginstatus opgeslagen en krijg je geen spam voor bestaande voorraad.
10. Daarna draait de workflow automatisch iedere 5 minuten.

## Hoe voorraadstatus wordt bewaard

`state.json` wordt alleen naar de repository teruggeschreven wanneer een voorraadstatus/productstatus verandert. Daardoor wordt niet bij iedere controle een nieuwe commit gemaakt.

## Veiligheid

- Zet de Discord webhook **nooit in `monitor.py`**.
- Gebruik alleen de GitHub Secret `DISCORD_WEBHOOK`.
- Als de webhook ooit openbaar wordt, maak hem opnieuw aan in Discord.

## Opmerking

GitHub geplande workflows kunnen incidenteel vertraagd worden. De minimale geplande interval is momenteel 5 minuten.
