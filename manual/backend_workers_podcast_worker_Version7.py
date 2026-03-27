async def generate_script_only(ctx: dict, job_id: str) -> dict:
    """Gera roteiros. Se tem tópicos manuais do marca-texto, usa eles.
    Se não tem, usa o Content Planner automático."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        # PASSO 1 — Lendo texto
        job.status = "READING"
        job.progress = 2
        job.current_step = "📄 Lendo texto de entrada..."
        db.commit()

        from backend.services.llm import get_provider

        text = job.input_text or ""
        llm_mode = job.llm_mode

        # ═══════════════════════════════════════════════════════
        # VERIFICAR SE TEM TÓPICOS MANUAIS (marca-texto)
        # ═══════════════════════════════════════════════════════
        user_topics = None
        if job.content_plan:
            try:
                parsed_topics = json.loads(job.content_plan)
                if (isinstance(parsed_topics, list)
                        and len(parsed_topics) > 0
                        and isinstance(parsed_topics[0], str)):
                    user_topics = parsed_topics
                    logger.info(f"Tópicos manuais do usuário: {user_topics}")
            except (json.JSONDecodeError, TypeError):
                pass

        # ═════════════���═════════════════════════════════════════
        # MODO 1: TÓPICOS MANUAIS (marca-texto do usuário)
        # ═══════════════════════════════════════════════════════
        if user_topics:
            total_episodes = len(user_topics)

            job.progress = 4
            job.current_step = f"🤖 Conectando ao provedor LLM ({llm_mode})..."
            db.commit()

            provider = get_provider(str(llm_mode))

            job.status = "LLM_PROCESSING"
            job.progress = 8
            job.current_step = (
                f"📌 {total_episodes} tópico(s) selecionado(s) pelo usuário"
            )
            db.commit()

            all_scripts = []
            previous_summary = ""
            total_segments = 0

            for i, topic_text in enumerate(user_topics):
                episode_num = i + 1

                # Progresso: 10% a 35% dividido entre episódios
                ep_progress = 10 + int((i / total_episodes) * 25)

                job.progress = ep_progress
                job.current_step = (
                    f"🧠 Gerando episódio {episode_num}/{total_episodes}: "
                    f"'{topic_text[:40]}'..."
                )
                db.commit()

                config = {
                    "target_duration": job.target_duration or 10,
                    "depth_level": job.depth_level,
                    "podcast_type": job.podcast_type,
                    "voice_host": job.voice_host,
                    "voice_cohost": job.voice_cohost,
                    "section_title": topic_text,
                    "episode_number": episode_num,
                    "total_episodes": total_episodes,
                    "previous_summary": previous_summary,
                }

                # ── Montar input com TEXTO COMPLETO + FOCO no tópico ──
                # CRÍTICO: Envia o texto original inteiro para manter contexto.
                # O LLM recebe instrução explícita de NÃO inventar fora do texto.
                episode_input = (
                    f"TÓPICO DESTE EPISÓDIO: {topic_text}\n\n"
                    f"INSTRUÇÃO OBRIGATÓRIA: Gere um episódio de podcast focado "
                    f"EXCLUSIVAMENTE no tópico '{topic_text}' dentro do contexto "
                    f"do texto abaixo. NÃO invente informações que não estejam no "
                    f"texto fornecido. Use APENAS o que o texto diz sobre "
                    f"'{topic_text}'. Se o texto não fala sobre isso, diga que "
                    f"não há informação suficiente.\n\n"
                )

                # Resumo do episódio anterior (sequencialidade)
                if previous_summary:
                    episode_input += (
                        f"RESUMO DO EPISÓDIO ANTERIOR: {previous_summary}\n"
                        f"Faça referência natural ao que foi discutido antes "
                        f"para criar continuidade.\n\n"
                    )

                # Referência ao próximo episódio
                if episode_num < total_episodes:
                    next_topic = user_topics[episode_num]
                    episode_input += (
                        f"PRÓXIMO EPISÓDIO será sobre: '{next_topic}'\n"
                        f"Na despedida, mencione que o próximo tema será esse "
                        f"para criar expectativa.\n\n"
                    )
                elif episode_num == total_episodes:
                    episode_input += (
                        f"ESTE É O ÚLTIMO EPISÓDIO da série de {total_episodes}. "
                        f"Na despedida, faça uma recapitulação geral de todos os "
                        f"tópicos abordados na série.\n\n"
                    )

                episode_input += f"TEXTO DE REFERÊNCIA:\n{text}"

                script = await provider.generate_script(episode_input, config)

                # Contabilizar segmentos
                ep_segments = (
                    len(script.get("segments", []))
                    if isinstance(script, dict) else 0
                )
                total_segments += ep_segments

                job.progress = 10 + int(((i + 1) / total_episodes) * 25)
                job.current_step = (
                    f"✅ Episódio {episode_num}/{total_episodes} gerado "
                    f"({ep_segments} falas): '{topic_text[:30]}'"
                )
                db.commit()

                # Extrair resumo para o próximo episódio (continuidade)
                if isinstance(script, dict):
                    segments = script.get("segments", [])
                    last_texts = [
                        s.get("text", "") for s in segments[-3:]
                        if s.get("text")
                    ]
                    previous_summary = " ".join(last_texts)[:500]
                    script["episode_number"] = episode_num
                    script["total_episodes"] = total_episodes
                    script["section_title"] = topic_text

                all_scripts.append(script)
                logger.info(
                    f"Episódio {episode_num}/{total_episodes} gerado: "
                    f"{topic_text}"
                )

            # ── Salvar roteiros ──
            job.progress = 36
            job.current_step = (
                f"✅ Validando {total_episodes} roteiro(s) "
                f"({total_segments} falas)..."
            )
            db.commit()

            job.progress = 38
            job.current_step = "💾 Salvando roteiros no banco de dados..."
            db.commit()

            if len(all_scripts) == 1:
                job.script_json = json.dumps(
                    all_scripts[0], ensure_ascii=False
                )
            else:
                job.script_json = json.dumps(
                    all_scripts, ensure_ascii=False
                )

            job.status = "SCRIPT_DONE"
            job.progress = 40
            job.current_step = (
                f"✅ Roteiro pronto ({total_episodes} episódios, "
                f"{total_segments} falas)"
            )
            db.commit()

            return {
                "success": True,
                "job_id": job_id,
                "total_episodes": total_episodes,
                "total_segments": total_segments,
                "script_json": job.script_json,
            }

        # ═══════════════════════════════════════════════════════
        # MODO 2: CONTENT PLANNER AUTOMÁTICO (sem tópicos manuais)
        # ═══════════════════════════════════════════════════════
        # Este é o comportamento ORIGINAL — quando o usuário NÃO
        # marcou nenhum tópico, o sistema decide automaticamente.

        job.progress = 4
        job.current_step = f"🤖 Conectando ao provedor LLM ({llm_mode})..."
        db.commit()

        provider = get_provider(str(llm_mode))

        # PASSO 3 — Planejamento de conteúdo automático
        job.progress = 6
        job.current_step = (
            "🧠 Analisando texto e identificando conceitos-chave..."
        )
        db.commit()

        from backend.services.simple_content_planner import (
            create_content_plan,
            format_plan_report,
        )

        plan = await create_content_plan(text, provider)
        logger.info(f"\n{format_plan_report(plan)}")

        total_episodes = plan.total_episodes

        # PASSO 4 — Plano criado
        job.status = "LLM_PROCESSING"
        job.progress = 10
        job.current_step = (
            f"📊 Plano criado: {total_episodes} episódio(s) | "
            f"~{plan.estimated_total_minutes} min total"
        )
        db.commit()

        # Salvar plano no job
        job.content_plan = json.dumps(
            {
                "total_episodes": plan.total_episodes,
                "estimated_total_minutes": plan.estimated_total_minutes,
                "episodes": [
                    {
                        "episode_number": ep.episode_number,
                        "title": ep.title,
                        "main_concept": ep.main_concept,
                        "key_topics": ep.key_topics,
                        "estimated_minutes": ep.estimated_minutes,
                    }
                    for ep in plan.episodes
                ],
            },
            ensure_ascii=False,
        )
        db.commit()

        # PASSO 5+ — Gerar cada episódio
        all_scripts = []
        previous_summary = ""
        total_segments = 0

        for i, ep_plan in enumerate(plan.episodes):
            episode_num = ep_plan.episode_number
            ep_progress = 10 + int((i / total_episodes) * 25)

            job.progress = ep_progress
            job.current_step = (
                f"🧠 Gerando episódio {episode_num}/{total_episodes}: "
                f"'{ep_plan.title[:40]}'..."
            )
            db.commit()

            config = {
                "target_duration": job.target_duration or 10,
                "depth_level": job.depth_level,
                "podcast_type": job.podcast_type,
                "voice_host": job.voice_host,
                "voice_cohost": job.voice_cohost,
                "section_title": ep_plan.title,
                "episode_number": episode_num,
                "total_episodes": total_episodes,
                "previous_summary": previous_summary,
                "focus_prompt": ep_plan.focus_prompt,
                "main_concept": ep_plan.main_concept,
                "key_topics": ep_plan.key_topics,
            }

            episode_input = (
                f"CONCEITO PRINCIPAL: {ep_plan.main_concept}\n\n"
                f"TÓPICOS PARA APROFUNDAR: "
                f"{', '.join(ep_plan.key_topics)}\n\n"
                f"INSTRUÇÃO DE FOCO: {ep_plan.focus_prompt}\n\n"
                f"TEXTO DE REFERÊNCIA:\n{text[:8000]}"
            )

            script = await provider.generate_script(episode_input, config)

            ep_segments = (
                len(script.get("segments", []))
                if isinstance(script, dict) else 0
            )
            total_segments += ep_segments

            job.progress = 10 + int(((i + 1) / total_episodes) * 25)
            job.current_step = (
                f"✅ Episódio {episode_num}/{total_episodes} gerado "
                f"({ep_segments} falas): '{ep_plan.title[:30]}'"
            )
            db.commit()

            if isinstance(script, dict):
                segments = script.get("segments", [])
                last_texts = [
                    s.get("text", "") for s in segments[-3:]
                    if s.get("text")
                ]
                previous_summary = " ".join(last_texts)[:500]
                script["episode_number"] = episode_num
                script["total_episodes"] = total_episodes
                script["section_title"] = ep_plan.title
                script["main_concept"] = ep_plan.main_concept

            all_scripts.append(script)
            logger.info(
                f"Episódio {episode_num}/{total_episodes} gerado: "
                f"{ep_plan.title}"
            )

        # Validar e salvar
        job.progress = 36
        job.current_step = (
            f"✅ Validando {total_episodes} roteiro(s) "
            f"({total_segments} falas)..."
        )
        db.commit()

        job.progress = 38
        job.current_step = "💾 Salvando roteiros no banco de dados..."
        db.commit()

        if len(all_scripts) == 1:
            job.script_json = json.dumps(
                all_scripts[0], ensure_ascii=False
            )
        else:
            job.script_json = json.dumps(
                all_scripts, ensure_ascii=False
            )

        job.status = "SCRIPT_DONE"
        job.progress = 40
        job.current_step = (
            f"✅ Roteiro pronto ({total_episodes} episódios, "
            f"{total_segments} falas, "
            f"~{plan.estimated_total_minutes} min)"
        )
        db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "total_episodes": total_episodes,
            "total_segments": total_segments,
            "script_json": job.script_json,
        }

    except Exception as e:
        logger.error(f"Job {job_id} falhou ao gerar roteiro: {e}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.current_step = f"❌ Erro: {str(e)[:100]}"
                db.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status failed: {db_err}")
        return {"success": False, "job_id": job_id, "error": str(e)}
    finally:
        db.close()