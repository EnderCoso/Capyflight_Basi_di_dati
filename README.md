# CapyFlights – Flight Booking System

>Progetto realizzato per il corso di **Basi di Dati** presso l'**Università Ca' Foscari di Venezia** (A.Y. 2024/2025).

CapyFlights è un'applicazione web progettata per la gestione completa delle prenotazioni aeree. Il sistema permette agli utenti di cercare voli, selezionare posti a sedere e gestire il proprio profilo, offrendo contemporaneamente alle compagnie aeree strumenti avanzati per l'inserimento di voli e il monitoraggio delle statistiche.

---

## 🛠️ Stack Tecnologico

Il sistema è sviluppato utilizzando tecnologie moderne per la gestione dei dati e del web:

* **Web Framework**: Flask 
* **ORM (Object-Relational Mapping)**: SQLAlchemy 
* **Database**: PostgreSQL 
* **Gestione Sessioni**: Tramite cookie (`user_id`, `user_type`)
---

## 🚀 Funzionalità Principali

### ✈️ Per i Passeggeri (Utenti e Anonimi)
* **Ricerca Avanzata**: Ricerca voli per partenza, destinazione e data, con copertura di un arco temporale di sette giorni
* **Soluzioni di Viaggio**: Supporto per voli diretti e voli con uno scalo
* **Filtri e Ordinamento**: Possibilità di ordinare i risultati per prezzo o durata
* **Prenotazione Completa**: Selezione del posto a sedere, scelta di eventuali extra e generazione del biglietto digitale (richiede autenticazione)
* **Area Personale**: Visualizzazione dei dati del profilo e dello storico dei biglietti acquistati

### 🏢 Per le Compagnie Aeree
* **Gestione Operativa**: Creazione e inserimento di nuovi voli nel sistema
* **Dashboard Statistica**: Monitoraggio in tempo reale del numero di passeggeri, ricavi totali e voli più richiesti

---

## 📊 Architettura dei Dati

Il database è strutturato per garantire l'integrità dei dati e l'efficienza delle query

***Gerarchia Utenti**: Utilizzo di una superclasse `Utente` che si specializza in `Passeggero` e `CompagniaAerea` per gestire uniformemente le credenziali
* **Integrità e Controlli**: 
    * Verifica della disponibilità dei posti in tempo reale per evitare conflitti di concorrenza
    * Vincoli su prezzi e importi (non negativi)
    * Coerenza temporale sulle date di acquisto dei biglietti
* **Ottimizzazione**: Ridondanza calcolata (es. `id_compagnia` nella tabella `Volo`) per migliorare le performance delle query ed evitare join non necessari
---
