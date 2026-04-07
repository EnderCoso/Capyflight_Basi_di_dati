# CapyFlights – Flight Booking System

> [cite_start]Progetto realizzato per il corso di **Basi di Dati** presso l'**Università Ca' Foscari di Venezia** (A.Y. 2024/2025)[cite: 1, 2, 7].

[cite_start]CapyFlights è un'applicazione web progettata per la gestione completa delle prenotazioni aeree[cite: 9]. [cite_start]Il sistema permette agli utenti di cercare voli, selezionare posti a sedere e gestire il proprio profilo, offrendo contemporaneamente alle compagnie aeree strumenti avanzati per l'inserimento di voli e il monitoraggio delle statistiche[cite: 9, 10].

---

## 🛠️ Stack Tecnologico

[cite_start]Il sistema è sviluppato utilizzando tecnologie moderne per la gestione dei dati e del web[cite: 240, 241, 242]:

* [cite_start]**Web Framework**: Flask [cite: 240]
* [cite_start]**ORM (Object-Relational Mapping)**: SQLAlchemy [cite: 241]
* [cite_start]**Database**: PostgreSQL [cite: 242]
* [cite_start]**Gestione Sessioni**: Tramite cookie (`user_id`, `user_type`) [cite: 228, 229]

---

## 🚀 Funzionalità Principali

### ✈️ Per i Passeggeri (Utenti e Anonimi)
* [cite_start]**Ricerca Avanzata**: Ricerca voli per partenza, destinazione e data, con copertura di un arco temporale di sette giorni[cite: 12, 13].
* [cite_start]**Soluzioni di Viaggio**: Supporto per voli diretti e voli con uno scalo[cite: 12, 173].
* [cite_start]**Filtri e Ordinamento**: Possibilità di ordinare i risultati per prezzo o durata[cite: 19].
* [cite_start]**Prenotazione Completa**: Selezione del posto a sedere, scelta di eventuali extra e generazione del biglietto digitale (richiede autenticazione)[cite: 22, 23, 24, 25].
* [cite_start]**Area Personale**: Visualizzazione dei dati del profilo e dello storico dei biglietti acquistati[cite: 232].

### 🏢 Per le Compagnie Aeree
* [cite_start]**Gestione Operativa**: Creazione e inserimento di nuovi voli nel sistema[cite: 27].
* [cite_start]**Dashboard Statistica**: Monitoraggio in tempo reale del numero di passeggeri, ricavi totali e voli più richiesti[cite: 28, 226].

---

## 📊 Architettura dei Dati

[cite_start]Il database è strutturato per garantire l'integrità dei dati e l'efficienza delle query[cite: 234].

* [cite_start]**Gerarchia Utenti**: Utilizzo di una superclasse `Utente` che si specializza in `Passeggero` e `CompagniaAerea` per gestire uniformemente le credenziali[cite: 90, 91].
* **Integrità e Controlli**: 
    * [cite_start]Verifica della disponibilità dei posti in tempo reale per evitare conflitti di concorrenza[cite: 235].
    * [cite_start]Vincoli su prezzi e importi (non negativi)[cite: 236].
    * [cite_start]Coerenza temporale sulle date di acquisto dei biglietti[cite: 237].
* [cite_start]**Ottimizzazione**: Ridondanza calcolata (es. `id_compagnia` nella tabella `Volo`) per migliorare le performance delle query ed evitare join non necessari[cite: 94, 97].

---

## 📦 Installazione ed Esecuzione

### Requisiti
* Python 3.x
* PostgreSQL

### Setup
1. **Configura il database**: Assicurati che PostgreSQL sia attivo e crea un database dedicato.
2. **Installa le dipendenze**:
   ```bash
   pip install flask sqlalchemy psycopg2
