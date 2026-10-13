-- FE014 · Sentimiento global generado por un flujo de insights con un LLM (T1).
-- Solo se escribe si Genesys no da el sentimiento de la conversación (`conversation.customer_sentiment`); la API lee
-- primero el de Genesys. Una redescarga con «Sobrescribir» lo vacía junto con el resto del análisis.
ALTER TABLE analysis ADD COLUMN sentiment real;
