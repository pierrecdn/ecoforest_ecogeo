[![SWUbanner](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua/)

Ecoforest EcoGeo heat pump integration PoC (proof of concept, thus may lack features or stability)
This is forked from @bytestorm [ecoforest_ecogeo integration](https://github.com/bytestorm/ecoforest_ecogeo/).
I didn't succeed to have that one working due to my HP24 Gateway software/API (check https://github.com/bytestorm/ecoforest_ecogeo/issues/16).
Consequently this fork is reintroducing a new client and integration.

To install, add the GitHub Repo using the button below:
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pierrecdn&repository=ecoforest_ecogeo&category=integration)

After installing the integration in HACS
- Restart Home Assistant
- Go to "Settings" -> "Devices & Services" -> "Add integration"
- Look for "Ecoforest EcoGeo/EcoAir" integration to start setting it up
- For "Ecoforest IP address" and Username/Password use those of the web interface address of your heat pump.
- Optionally, you can specify an alias that will be used instead of the model name to generate entity prefixes
