@router.post("/paste")
async def upload_paste(
    title: str,
    text: str,
    llm_mode: str = "gemini-2.5-flash",
    voice_host: str = "pf_dora",
    voice_cohost: str | None = None,
    podcast_type: str = "monologue",
    target_duration: int = 10,
    depth_level: str = "normal",
    pipeline_mode: bool = False,
    topics: str | None = None,           # ← NOVO: JSON array de tópicos do marca-texto
    db: Session = Depends(get_db),
):
    if not text or len(text.strip()) < 100:
        raise HTTPException(
            status_code=400, detail="Texto muito curto (mínimo 100 caracteres)"
        )

    # ← NOVO: Validar topics se fornecido
    validated_topics = None
    if topics:
        try:
            import json
            parsed = json.loads(topics)
            if isinstance(parsed, list) and all(isinstance(t, str) for t in parsed):
                if len(parsed) > 10:
                    raise HTTPException(
                        status_code=400, detail="Máximo 10 tópicos permitidos"
                    )
                validated_topics = topics  # Manter como string JSON
                logger.info(f"Tópicos manuais recebidos: {parsed}")
        except json.JSONDecodeError:
            logger.warning(f"Topics inválido (não é JSON): {topics}")
            validated_topics = None

    job_id = str(uuid.uuid4())

    job = Job(
        id=job_id,
        title=title,
        status="PENDING",
        progress=0,
        current_step="Texto enviado, aguardando processamento...",
        input_text=text,
        llm_mode=llm_mode,
        voice_host=voice_host,
        voice_cohost=voice_cohost,
        podcast_type=podcast_type,
        target_duration=target_duration,
        depth_level=depth_level,
        pipeline_mode=pipeline_mode,
        content_plan=validated_topics,     # ← NOVO: Salvar tópicos na coluna existente
    )
    db.add(job)
    db.commit()

    return {"job_id": job_id, "status": "uploaded", "char_count": len(text)}