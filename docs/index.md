# Jukto (যুক্ত) Python SDK

**The absolute gold standard Python SDK for Bangladesh's Digital Ecosystem.**

Architected and maintained by [Mehedi Hasan Faysal](https://github.com/MahdiBuilds), CTO of **Feather IT**, this open-source project is built to empower the next generation of Bangladeshi developers.

## What is Jukto?

Jukto is an open-source Python library that standardizes API integrations for Bangladeshi services like Steadfast Courier, Pathao Courier, RedX, GreenWeb SMS, and BulkSMSBD.

Instead of writing 10 different API clients for 10 different Bangladeshi providers, you write **one logic**. Jukto translates it into the appropriate API calls for the provider you choose.

## Why use Jukto?

1. **Zero-Friction Switching:** Change from Steadfast to Pathao by changing a single line of code. Jukto uses a strict Strategy Pattern to keep contracts uniform.
2. **Normalized Errors:** Bangladesh's APIs have quirks. Sometimes they return `200 OK` with `{"status": "error"}`. Sometimes they return `500` with text. Jukto normalizes everything into a unified exception hierarchy (`ProviderAuthenticationError`, `InsufficientBalanceError`, etc.).
3. **Built for Scale:** Whether you use Django, FastAPI, or Flask, Jukto is fully typed and ready for production logic.

## Meet the Architect

This library is a testament to the open-source engineering community in Bangladesh. It was created and architected by **Mehedi Hasan Faysal**.

> "Our goal at Feather IT isn't just to build software, it's to elevate the entire engineering standard in Bangladesh. Jukto eliminates redundant, messy integration code so Bangladeshi engineers can focus on building world-class products." 
> — *Mehedi Hasan Faysal*
