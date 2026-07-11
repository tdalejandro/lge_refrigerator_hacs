# LGE Refrigerator

<p align="center">
  <img src="assets/logo.webp" alt="LGE Refrigerator" width="160">
</p>

Integración HACS independiente para **refrigeradores LG ThinQ Wi-Fi**. No crea
entidades para lavadoras, aires acondicionados ni ningún otro equipo LG.

Incluye un accesorio HomeKit nativo: Casa ve un solo `Refrigerador` con sus
servicios agrupados, sin usar el puente genérico de Home Assistant y sin un
segundo sondeo de LG.

## Entidades

Por cada refrigerador seleccionado crea:

- `climate`: Fridge y Freezer, con rango real del modelo y control de objetivo.
- `binary_sensor`: Door open.
- `sensor`: Fridge temperature y Freezer temperature.
- `switch`: Ice Plus, Express Freezer, Express Fridge y Eco Friendly, solo si el
  modelo los expone.
- `sensor`: Water filter remaining y Fresh air filter remaining, solo si el
  modelo los expone.

En HomeKit se presenta como un solo accesorio con dos termostatos, el sensor de
puerta, los interruptores disponibles y mantenimiento de filtro de agua cuando
el modelo lo soporta.

## Instalación con HACS

1. HACS → Integraciones → menú ⋮ → **Repositorios personalizados**.
2. Añade `https://github.com/tdalejandro/lge-refrigerator` con categoría
   **Integration**.
3. Instala **LGE Refrigerator** y reinicia Home Assistant.
4. Ajustes → Dispositivos y servicios → Añadir integración → **LGE Refrigerator**.

El flujo pide país e idioma de la cuenta LG ThinQ. Para cuentas creadas con
Google, Apple, Facebook o Amazon, activa el inicio mediante navegador. La
contraseña no se guarda: Home Assistant conserva solamente el token renovable de
LG.

El puerto HomeKit predeterminado es `21100`. Tras crear la entrada, el código de
emparejamiento aparece como notificación persistente de Home Assistant.

## Límites de LG

LG puede bloquear temporalmente cuentas con sondeo demasiado frecuente. La
integración fija un intervalo de 300 segundos y comparte ese único estado con
las entidades HA y el accesorio HomeKit.

Antes de activar esta integración, desactiva o elimina la instancia anterior de
SmartThinQ que use la misma cuenta, para no duplicar llamadas a LG.

## Créditos y licencia

El cliente ThinQ vendorizado procede de
[ollo69/ha-smartthinq-sensors](https://github.com/ollo69/ha-smartthinq-sensors).
El diseño de servicios de refrigerador toma como referencia
[nVuln/homebridge-lg-thinq](https://github.com/nVuln/homebridge-lg-thinq).
Ambos se distribuyen bajo Apache-2.0; consulta [NOTICE](NOTICE).
