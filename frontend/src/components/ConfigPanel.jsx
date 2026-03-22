import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './ConfigPanel.css';

function ConfigPanel({ onClose }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  
  const [usuarioNome, setUsuarioNome] = useState('');
  const [pessoasProximas, setPessoasProximas] = useState([{ nome: '', relacao: '' }]);
  const [apresentador, setApresentador] = useState({ nome: '', voz: 'pt-BR-FranciscaNeural' });
  const [apresentadora, setApresentadora] = useState({ nome: '', voz: 'pt-BR-DeboraNeural' });
  const [personagens, setPersonagens] = useState(Array(10).fill({ nome: '', cargo: '', empresa: '' }));
  const [empresas, setEmpresas] = useState(Array(10).fill(''));
  const [opcoes, setOpcoes] = useState({
    saudar: true,
    mencionar: true,
    despedida: true
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await axios.get('http://localhost:8000/config/');
      const data = response.data;
      
      setUsuarioNome(data.usuario_nome || '');
      
      if (data.pessoas_proximas && data.pessoas_proximas.length > 0) {
        setPessoasProximas(data.pessoas_proximas);
      }
      
      if (data.apresentador) {
        setApresentador(data.apresentador);
      }
      
      if (data.apresentadora) {
        setApresentadora(data.apresentadora);
      }
      
      if (data.personagens && data.personagens.length > 0) {
        const filled = [...personagens];
        data.personagens.forEach((p, i) => {
          if (i < 10) filled[i] = p;
        });
        setPersonagens(filled);
      }
      
      if (data.empresas && data.empresas.length > 0) {
        const filled = [...empresas];
        data.empresas.forEach((e, i) => {
          if (i < 10) filled[i] = e;
        });
        setEmpresas(filled);
      }
      
      setOpcoes({
        saudar: data.saudar_nome !== false,
        mencionar: data.mencionar_pessoas !== false,
        despedida: data.despedida_personalizada !== false
      });
      
    } catch (error) {
      console.error('Erro ao carregar config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        usuario_nome: usuarioNome,
        pessoas_proximas: pessoasProximas.filter(p => p.nome.trim()),
        apresentador: apresentador,
        apresentadora: apresentadora,
        personagens: personagens.filter(p => p.nome.trim()),
        empresas: empresas.filter(e => e.trim()),
        saudar_nome: opcoes.saudar,
        mencionar_pessoas: opcoes.mencionar,
        despedida_personalizada: opcoes.despedida
      };
      await axios.post('http://localhost:8000/config/', payload);
      
      window.dispatchEvent(new Event('config-saved'));
      setSaved(true);
      setTimeout(() => onClose(), 1000);
      
    } catch (error) {
      console.error('Erro ao salvar:', error);
      alert('Erro: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSaving(false);
    }
  };

  const updatePessoa = (index, field, value) => {
    const updated = [...pessoasProximas];
    updated[index] = { ...updated[index], [field]: value };
    setPessoasProximas(updated);
  };

  const updatePersonagem = (index, field, value) => {
    const updated = [...personagens];
    updated[index] = { ...updated[index], [field]: value };
    setPersonagens(updated);
  };

  const updateEmpresa = (index, value) => {
    const updated = [...empresas];
    updated[index] = value;
    setEmpresas(updated);
  };

  if (loading) {
    return (
      <div className="config-overlay">
        <div className="config-modal">
          <div className="loading">Carregando...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="config-overlay">
      <div className="config-modal">
        <div className="config-header">
          <h2>⚙️ Personalizar Podcast</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <div className="config-body">
          <div className="config-section">
            <h3>👤 Quem vai ouvir</h3>
            <input
              type="text"
              placeholder="Nome de quem vai ouvir o podcast"
              value={usuarioNome}
              onChange={(e) => setUsuarioNome(e.target.value)}
            />
          </div>

          <div className="config-section">
            <h3>💝 Pessoas Próximas (afetivo)</h3>
            <p className="hint">Ex: mãe, pai, esposa, filho, amigo...</p>
            {pessoasProximas.map((pessoa, i) => (
              <div key={i} className="row-group">
                <input
                  type="text"
                  placeholder="Nome"
                  value={pessoa.nome}
                  onChange={(e) => updatePessoa(i, 'nome', e.target.value)}
                />
                <select
                  value={pessoa.relacao}
                  onChange={(e) => updatePessoa(i, 'relacao', e.target.value)}
                >
                  <option value="">Relação</option>
                  <option value="mãe">mãe</option>
                  <option value="pai">pai</option>
                  <option value="esposa">esposa</option>
                  <option value="marido">marido</option>
                  <option value="filho">filho</option>
                  <option value="filha">filha</option>
                  <option value="amigo">amigo</option>
                  <option value="amiga">amiga</option>
                  <option value="irmão">irmão</option>
                  <option value="irmã">irmã</option>
                </select>
              </div>
            ))}
          </div>

          <div className="config-section">
            <h3>🎙️ Apresentador (Host)</h3>
            <div className="row-group">
              <input
                type="text"
                placeholder="Nome do apresentador"
                value={apresentador.nome}
                onChange={(e) => setApresentador({...apresentador, nome: e.target.value})}
              />
              <select
                value={apresentador.voz}
                onChange={(e) => setApresentador({...apresentador, voz: e.target.value})}
              >
                <option value="pt-BR-FranciscaNeural">Francisca (feminina)</option>
                <option value="pt-BR-AntonioNeural">Antônio (masculina)</option>
                <option value="pt-BR-DeboraNeural">Débora (feminina)</option>
                <option value="pt-BR-DonatoNeural">Donato (masculina)</option>
                <option value="pt-BR-BrendaNeural">Brenda (feminina)</option>
                <option value="pt-BR-RaquelNeural">Raquel (feminina)</option>
              </select>
            </div>
          </div>

          <div className="config-section">
            <h3>🎙️ Apresentadora (Co-host)</h3>
            <div className="row-group">
              <input
                type="text"
                placeholder="Nome da apresentadora"
                value={apresentadora.nome}
                onChange={(e) => setApresentadora({...apresentadora, nome: e.target.value})}
              />
              <select
                value={apresentadora.voz}
                onChange={(e) => setApresentadora({...apresentadora, voz: e.target.value})}
              >
                <option value="pt-BR-DeboraNeural">Débora (feminina)</option>
                <option value="pt-BR-FranciscaNeural">Francisca (feminina)</option>
                <option value="pt-BR-BrendaNeural">Brenda (feminina)</option>
                <option value="pt-BR-RaquelNeural">Raquel (feminina)</option>
              </select>
            </div>
          </div>

          <div className="config-section">
            <h3>👥 Personagens (exemplos para variar)</h3>
            <p className="hint">Ex: Ana - Caixa - Magazine Luiza</p>
            <div className="personagens-grid">
              {personagens.map((p, i) => (
                <div key={i} className="personagem-row">
                  <input
                    type="text"
                    placeholder="Nome"
                    value={p.nome}
                    onChange={(e) => updatePersonagem(i, 'nome', e.target.value)}
                  />
                  <input
                    type="text"
                    placeholder="Cargo"
                    value={p.cargo}
                    onChange={(e) => updatePersonagem(i, 'cargo', e.target.value)}
                  />
                  <input
                    type="text"
                    placeholder="Empresa"
                    value={p.empresa}
                    onChange={(e) => updatePersonagem(i, 'empresa', e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="config-section">
            <h3>🏢 Empresas (exemplos para variar)</h3>
            <div className="empresas-grid">
              {empresas.map((emp, i) => (
                <input
                  key={i}
                  type="text"
                  placeholder={`Empresa ${i + 1}`}
                  value={emp}
                  onChange={(e) => updateEmpresa(i, e.target.value)}
                />
              ))}
            </div>
          </div>

          <div className="config-section">
            <h3>📝 Opções</h3>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={opcoes.saudar}
                onChange={(e) => setOpcoes({...opcoes, saudar: e.target.checked})}
              />
              Saudar pelo nome no início
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={opcoes.mencionar}
                onChange={(e) => setOpcoes({...opcoes, mencionar: e.target.checked})}
              />
              Mencionar pessoas próximas nos exemplos
            </label>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={opcoes.despedida}
                onChange={(e) => setOpcoes({...opcoes, despedida: e.target.checked})}
              />
              Despedida personalizada
            </label>
          </div>
        </div>

        <div className="config-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Salvando...' : saved ? '✅ Salvo!' : '💾 Salvar Configuração'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfigPanel;
