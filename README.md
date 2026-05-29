# ZeroOneHack_01
Project for Zero One Hack, Vienna 05/2025

# Forecast-Driven Business Launch Agent

## 1. Kurzbeschreibung

Unsere Idee ist ein **Forecast-Driven Business Launch Agent**.

Die Anwendung hilft zukünftigen Geschäftsinhabern dabei, eine Geschäftsidee an einem konkreten Standort datenbasiert zu bewerten. Nutzer können über ein detailliertes UI ihre Idee beschreiben, zum Beispiel:

> “Ich möchte einen Premium-Weinshop im 1. Bezirk in Wien eröffnen.”

Das System analysiert anschließend, ob diese Idee wirtschaftlich sinnvoll ist. Dafür werden probabilistische Forecasts, lokale Marktannahmen, Mockdaten, Kostenstrukturen und Business-Logik kombiniert.

Am Ende gibt das System eine klare Empfehlung:

* **Launch**
* **Adapt concept**
* **Delay / change location**
* **Do not launch**

Wichtig: Die Sybilion API liefert nicht direkt die finale Geschäftsentscheidung. Sie liefert Forecasts, Unsicherheiten, Treiber und Backtest-Daten. Unsere eigene Anwendung baut darauf die Entscheidungsschicht.

---

## 2. Problem

Viele Menschen haben Geschäftsideen, wissen aber nicht, ob diese an einem bestimmten Standort wirtschaftlich sinnvoll sind.

Typische Fragen sind:

* Gibt es genug Nachfrage?
* Ist der Standort passend?
* Sind die Fixkosten zu hoch?
* Wie stark ist die Konkurrenz?
* Wie wirkt sich Saisonalität aus?
* Was passiert, wenn Miete oder Personalkosten steigen?
* Welche externen Faktoren beeinflussen die Erfolgschance?

Aktuelle Tools liefern oft nur statische Analysen oder grobe Marktinformationen. Unser Agent soll dagegen dynamisch, probabilistisch und entscheidungsorientiert arbeiten.

---

## 3. Lösung

Wir bauen eine Webanwendung, in der Nutzer ihre Geschäftsidee strukturiert eingeben können.

Beispiel:

```text
Business type: Premium wine shop
Location: Vienna 1st district
Target customers: tourists, locals, restaurants, corporate gifts
Business model: retail + tastings + online delivery
Initial investment: €120,000
Monthly rent: €8,000
Staff costs: €12,000
Average basket size: €42
Gross margin: 35%
Forecast horizon: 6 months
Competition level: medium-high
Foot traffic: high
Tourism dependency: high
```

Die Anwendung kombiniert diese Angaben mit:

* Forecasts aus der Sybilion API
* lokalen Mockdaten
* Kostenannahmen
* Nachfrageannahmen
* Wettbewerbsdruck
* Standortfaktoren
* Risikoregeln
* Break-even-Analyse
* Szenario-Simulation

---

## 4. Beispiel-Use-Case

### Szenario

Ein Gründer möchte einen Premium-Weinshop im 1. Bezirk in Wien eröffnen.

Der Standort hat:

* hohe Touristenfrequenz
* hohe Kaufkraft
* hohe Mieten
* starke Konkurrenz
* Potenzial für Premium-Produkte
* Potenzial für Tastings, Firmenkunden und Geschenkkörbe

### Forecast-Signale

Die Sybilion API kann relevante Marktindikatoren prognostizieren, zum Beispiel:

* Tourismusnachfrage
* Premium-Retail-Spending
* Konsumverhalten
* Kostendruck
* saisonale Nachfrage
* allgemeine Retail-Entwicklung

Die API liefert dabei nicht nur einen einzelnen Wert, sondern probabilistische Ergebnisse:

* Downside-Szenario
* Base-Szenario
* Upside-Szenario
* Confidence Bands
* wichtige externe Treiber
* Backtest-Metriken

---

## 5. Rolle der Sybilion API

Die Sybilion API ist der Forecasting-Layer.

Sie nimmt eine monatliche Zeitreihe und Kontext-Keywords entgegen und liefert:

* probabilistische Monats-Forecasts
* Forecast-Bands, z. B. p10, p50, p90
* externe Treiber mit Importance Scores
* Backtest Accuracy Metrics

Beispielhafte Treiber:

```text
Tourism demand
Premium retail spending
Rent pressure
Competition density
Seasonality
Consumer spending
```

Unsere Anwendung nutzt diese API-Ergebnisse, um daraus konkrete Entscheidungen abzuleiten.

---

## 6. Was unser eigener Agent macht

Unser Agent ist die Entscheidungsschicht über der Forecasting API.

Er berechnet unter anderem:

* erwarteten Umsatz
* erwarteten Rohertrag
* operative Kosten
* erwarteten Monatsgewinn
* Downside-Risiko
* Upside-Potenzial
* Break-even-Wahrscheinlichkeit
* Risikoadjustierten Gewinn
* Standort-Fit
* Entscheidungsempfehlung

Beispielhafte Logik:

```text
base_demand = forecast_p50 × foot_traffic_index × location_multiplier

monthly_revenue = base_demand × average_basket_size

gross_profit = monthly_revenue × gross_margin

operating_profit = gross_profit - rent - staff_costs - other_fixed_costs

risk_adjusted_profit =
    operating_profit
    - uncertainty_penalty
    - competition_penalty
    - rent_pressure_penalty
```

Die finale Entscheidung basiert also nicht auf einem LLM, sondern auf nachvollziehbarer Business-Logik.

---

## 7. Entscheidungsempfehlungen

Der Agent gibt eine von vier Empfehlungen aus:

### 1. Launch

Die Geschäftsidee ist unter den aktuellen Annahmen wirtschaftlich attraktiv.

Beispiel:

```text
Break-even probability: 82%
Risk-adjusted profit: positive
Recommendation: Launch
```

### 2. Adapt concept

Die Idee hat Potenzial, aber das aktuelle Konzept ist zu riskant oder nicht optimal.

Beispiel:

```text
Recommendation: Adapt concept

Reason:
A pure retail wine shop is risky due to high rent and competition.
Adding tastings, B2B restaurant supply, corporate gifts and online delivery improves viability.
```

### 3. Delay / change location

Die Idee könnte funktionieren, aber nicht unter den aktuellen Marktbedingungen oder am aktuellen Standort.

Beispiel:

```text
Recommendation: Delay or change location

Reason:
Demand is currently uncertain and cost pressure is too high.
```

### 4. Do not launch

Die Idee ist unter den aktuellen Annahmen wirtschaftlich nicht attraktiv.

Beispiel:

```text
Recommendation: Do not launch

Reason:
The downside scenario becomes unprofitable and the break-even probability is too low.
```

---

## 8. Warum die Idee zum Forecasting AI Track passt

Der Track verlangt nicht, dass wir ein eigenes Forecasting-Modell trainieren. Die Sybilion API liefert den Forecast.

Unsere Aufgabe ist es, darauf einen **Decision Agent** zu bauen.

| Track-Anforderung      | Unsere Umsetzung                                           |
| ---------------------- | ---------------------------------------------------------- |
| Probabilistic forecast | Forecasts mit p10, p50, p90                                |
| Driver importance      | Anzeige wichtiger Treiber wie Tourismus, Miete, Konkurrenz |
| Decision change        | Forecast beeinflusst Launch/No-Launch-Entscheidung         |
| Visible reasoning      | Break-even, Treiber, Kosten und Risiken werden sichtbar    |
| Adaptive behavior      | Annahmen können live verändert werden                      |
| Substantive logic      | Eigene Decision Engine, keine reine LLM-Zusammenfassung    |
| Live demo              | Szenario kann auf der Bühne verändert werden               |

---

## 9. Live-Demo-Idee

### Schritt 1: Default-Szenario laden

```text
Business: Premium wine shop
Location: Vienna 1st district
Rent: €8,000/month
Staff costs: €12,000/month
Average basket size: €42
Gross margin: 35%
```

### Schritt 2: Analyse starten

Das System zeigt:

* Forecast mit Confidence Bands
* Driver Importance Chart
* Break-even-Wahrscheinlichkeit
* erwarteten Monatsgewinn
* finale Empfehlung

### Schritt 3: Erste Empfehlung

Beispiel:

```text
Recommendation: Adapt concept

Reason:
The location has strong demand potential due to tourism and premium retail spending.
However, high rent and competition make a pure retail concept risky.
The agent recommends adding tastings, B2B sales and corporate gift packages.
```

### Schritt 4: Live-Annahme ändern

Die Jury oder das Team ändert eine Annahme:

```text
Monthly rent increases from €8,000 to €13,000.
```

### Schritt 5: Agent reagiert

Das System berechnet neu:

```text
Break-even probability drops from 67% to 48%.

Recommendation changes from:
Adapt concept

to:
Do not launch / change location
```

### Schritt 6: Konzept verbessern

Dann wird das Geschäftsmodell angepasst:

```text
Average basket size increases from €42 to €58.
Additional tasting revenue is added.
```

### Schritt 7: Empfehlung verbessert sich

```text
Break-even probability increases again.
Recommendation changes to:
Adapt concept / Launch conditionally
```

Dadurch zeigen wir genau das, was der Track sehen will:

* Forecast verändert die Entscheidung
* Reasoning ist sichtbar
* Agent passt sich an neue Annahmen an

---

## 10. Geplanter Tech Stack

### Frontend

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui
* Plotly.js oder Recharts

### Backend

* FastAPI
* Python
* pandas
* numpy
* httpx
* Pydantic

### Daten

* Sybilion API
* Mockdaten für Standort und Business-Annahmen
* JSON-Dateien für MVP
* gecachte Forecast-Artefakte als Fallback

### Decision Engine

Eigene Python-Logik für:

* Umsatzberechnung
* Kostenberechnung
* Break-even-Wahrscheinlichkeit
* Risikobewertung
* Szenario-Simulation
* Empfehlung

### Optional

* LLM nur für verständliche Erklärung
* nicht für die eigentliche Entscheidung

---

## 11. Geplante Architektur

```text
Frontend UI
  ↓
Business Idea Form
  ↓
FastAPI Backend
  ↓
Sybilion API Client
  ↓
Forecast Parser
  ↓
Decision Engine
  ↓
Scenario Engine
  ↓
Dashboard + Explanation Layer
```

---

## 12. Wichtige Komponenten

### BusinessForm

Nutzer geben ihre Geschäftsidee ein.

### ForecastChart

Zeigt Forecast mit Unsicherheit:

* p10
* p50
* p90
* Confidence Band

### DriverImportanceChart

Zeigt, welche Faktoren die Prognose treiben.

### DecisionCard

Zeigt die finale Empfehlung:

* Launch
* Adapt concept
* Delay
* Do not launch

### ReasoningPanel

Zeigt, warum die Entscheidung getroffen wurde.

### ScenarioControls

Erlaubt Live-Anpassungen:

* Miete erhöhen
* Konkurrenz erhöhen
* Foot Traffic senken
* Warenkorb erhöhen
* Marge verändern
* Kostenschock simulieren
* Nachfrageschock simulieren

---

## 13. Warum unsere Idee stark ist

Unsere Idee ist stark, weil sie:

* ein reales Problem löst
* leicht verständlich ist
* gut demonstrierbar ist
* Forecasting sinnvoll nutzt
* Unsicherheit sichtbar macht
* konkrete Entscheidungen erzeugt
* nicht nur eine Chatbot-Zusammenfassung ist
* eigene Business- und Decision-Logik enthält
* live auf Änderungen reagieren kann
* auf viele Geschäftsideen skalierbar ist

---

## 14. Wichtigster Pitch-Satz

```text
The Sybilion API forecasts relevant market signals. Our agent translates those probabilistic forecasts into transparent business launch decisions.
```

Oder kürzer:

```text
We turn probabilistic forecasts into go/no-go business decisions for future entrepreneurs.
```

---

## 15. MVP-Ziel

Unser MVP soll mindestens Folgendes können:

* Default Use Case: Premium-Weinshop im 1. Bezirk in Wien
* detailliertes Eingabeformular
* Mockdaten für Standort und Business-Faktoren
* Sybilion API Integration oder Mock-Fallback
* Forecast mit Confidence Bands
* Driver Importance Anzeige
* eigene Decision Engine
* Break-even-Wahrscheinlichkeit
* finale Empfehlung
* Live-Szenarioänderung
* sichtbare Änderung der Empfehlung

---

## 16. Mögliche Erweiterungen

Später könnte das System weitere Geschäftsideen unterstützen:

* Café
* Fitnessstudio
* Tankstelle
* Boutique
* Restaurant
* Bäckerei
* Coworking Space
* Beauty Salon
* Mobility Hub

Außerdem könnten mehrere Standorte verglichen werden:

```text
Vienna 1st district vs Vienna 7th district vs Vienna 16th district
```

Das würde die Anwendung noch stärker machen, ist aber für den MVP nicht notwendig.

---

## 17. Zusammenfassung

Wir bauen keinen einfachen Forecast-Viewer und keinen simplen Chatbot.

Wir bauen einen **Decision Agent**, der Forecasts, Unsicherheit, Treiber, Standortannahmen und Business-Logik kombiniert, um Gründern zu helfen, bessere Entscheidungen zu treffen.

Der Kern der Idee:

```text
Business idea + location + forecast + uncertainty + decision logic
=
transparent launch recommendation
```

