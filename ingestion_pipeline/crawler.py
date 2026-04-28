"""Sitemap crawler for discovering documentation URLs.

This module implements the SitemapCrawler class responsible for:
- Fetching sitemap.xml files with retry logic
- Parsing XML to extract URLs
- Filtering URLs to include only documentation pages
- Excluding non-documentation pages (terms, privacy, contact, etc.)
- Intelligent SPA discovery using Playwright for JavaScript-loaded content

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

import logging
import requests
import asyncio
import re
from typing import List, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote

from .utils import retry_with_backoff

logger = logging.getLogger(__name__)


class SitemapCrawler:
    """Crawler for discovering documentation URLs from sitemap.xml.
    
    This class fetches and parses sitemap.xml files, extracting URLs that match
    documentation patterns while filtering out non-documentation pages.
    
    URL Filtering Rules:
        - Include: URLs matching /senior-x/* or /produto/*
        - Exclude: URLs containing: termos-de-uso, politica-privacidade, contato, home, sobre
    
    Attributes:
        sitemap_url: URL of the sitemap.xml to crawl
    """
    
    def __init__(self, sitemap_url: str):
        """Initialize crawler with sitemap URL.
        
        Args:
            sitemap_url: URL of the sitemap.xml file to crawl
        """
        self.sitemap_url = sitemap_url
        logger.info(f"Initialized SitemapCrawler with URL: {sitemap_url}")
    
    def fetch_sitemap(self) -> str:
        """Fetch sitemap XML content with retry logic.
        
        Uses exponential backoff retry strategy (3 attempts: 1s, 2s, 4s delays)
        to handle transient network failures.
        
        Returns:
            str: Raw XML content of the sitemap
            
        Raises:
            requests.RequestException: If all retry attempts fail
        """
        logger.info(f"Fetching sitemap from: {self.sitemap_url}")
        
        def _fetch():
            response = requests.get(
                self.sitemap_url,
                timeout=30,
                headers={'User-Agent': 'Senior-Training-OS-Ingestion-Pipeline/1.0'}
            )
            response.raise_for_status()
            return response.text
        
        try:
            xml_content = retry_with_backoff(
                func=_fetch,
                max_retries=3,
                delays=[1, 2, 4],
                exceptions=(requests.RequestException,)
            )
            logger.info(f"Successfully fetched sitemap ({len(xml_content)} bytes)")
            return xml_content
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch sitemap after retries: {e}")
            raise
    
    def parse_sitemap(self, xml_content: str) -> List[str]:
        """Parse XML and extract all URLs.
        
        Uses BeautifulSoup with lxml parser to extract <loc> tags from the sitemap.
        
        Args:
            xml_content: Raw XML content of the sitemap
            
        Returns:
            List[str]: List of all URLs found in the sitemap
        """
        logger.info("Parsing sitemap XML")
        
        try:
            soup = BeautifulSoup(xml_content, 'lxml-xml')
            
            # Extract all <loc> tags (URL locations in sitemap)
            loc_tags = soup.find_all('loc')
            urls = [loc.get_text().strip() for loc in loc_tags if loc.get_text().strip()]
            
            logger.info(f"Extracted {len(urls)} URLs from sitemap")
            return urls
            
        except Exception as e:
            logger.error(f"Failed to parse sitemap XML: {e}")
            return []
    
    def filter_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs to include only documentation pages.
        
        Applies filtering rules:
        1. Include only URLs ending with .htm or .html (documentation pages)
        2. Exclude PDFs, images, and other non-HTML files
        3. Exclude URLs containing keywords: termos-de-uso, politica-privacidade,
           contato, robots.txt, favicon
        
        Args:
            urls: List of URLs to filter
            
        Returns:
            List[str]: Filtered list containing only documentation URLs
        """
        logger.info(f"Filtering {len(urls)} URLs")
        
        # Keywords to exclude
        exclude_keywords = [
            'termos-de-uso',
            'politica-privacidade',
            'contato',
            'robots.txt',
            'favicon.ico',
            'suporte.exe'
        ]
        
        # File extensions to exclude
        exclude_extensions = [
            '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.exe', '.zip', '.rar', '.css', '.js', '.xml', '.txt'
        ]
        
        filtered_urls = []
        
        for url in urls:
            url_lower = url.lower()
            
            # Check if URL contains any exclude keyword
            if any(keyword in url_lower for keyword in exclude_keywords):
                logger.debug(f"Excluded (keyword): {url}")
                continue
            
            # Check if URL has excluded extension
            if any(url_lower.endswith(ext) for ext in exclude_extensions):
                logger.debug(f"Excluded (extension): {url}")
                continue
            
            # Include only .htm or .html files (documentation pages)
            if url_lower.endswith('.htm') or url_lower.endswith('.html'):
                filtered_urls.append(url)
                logger.debug(f"Included: {url}")
            else:
                logger.debug(f"Excluded (not HTML): {url}")
        
        logger.info(f"Filtered to {len(filtered_urls)} documentation URLs")
        return filtered_urls
    
    def crawl(self) -> List[str]:
        """Execute full crawl: fetch → parse → filter + important URLs + SPA discovery.
        
        Orchestrates the complete crawling workflow:
        1. Fetch sitemap XML with retry logic
        2. Parse XML to extract URLs
        3. Filter URLs to keep only documentation pages
        4. Add manually discovered important URLs
        5. Discover additional URLs from SPAs using Playwright
        
        Returns:
            List[str]: List of filtered documentation URLs + important URLs + SPA URLs
            
        Raises:
            requests.RequestException: If sitemap fetch fails after retries
        """
        logger.info("Starting sitemap crawl")
        
        try:
            # Fetch sitemap XML
            xml_content = self.fetch_sitemap()
            
            # Parse XML to extract URLs
            urls = self.parse_sitemap(xml_content)
            
            # Filter URLs to keep only documentation pages
            filtered_urls = self.filter_urls(urls)
            
            # Add manually discovered important URLs
            important_urls = self.get_important_urls()
            
            # Discover additional URLs from SPAs
            spa_urls = self.discover_spa_urls_sync()
            
            # Combine and deduplicate
            all_urls = list(set(filtered_urls + important_urls + spa_urls))
            
            logger.info(f"Crawl completed: {len(filtered_urls)} sitemap URLs + {len(important_urls)} important URLs + {len(spa_urls)} SPA URLs = {len(all_urls)} total URLs")
            return all_urls
            
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            # Return empty list on fatal failure (don't crash the pipeline)
            return []
    
    def discover_spa_urls_sync(self) -> List[str]:
        """Synchronous wrapper for SPA discovery.
        
        Handles event loop detection and runs SPA discovery appropriately.
        
        Returns:
            List[str]: List of discovered SPA URLs
        """
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, skip SPA discovery for now
                logger.warning("Already in event loop, skipping SPA discovery. Use discover_spa_urls() directly in async context.")
                return []
            except RuntimeError:
                # No event loop, safe to use asyncio.run()
                return asyncio.run(self.discover_spa_urls())
        except Exception as e:
            logger.error(f"SPA discovery failed: {e}")
            return []
    
    def get_important_urls(self) -> List[str]:
        """Get manually discovered important URLs including comprehensive ERP mapping.
        
        Returns:
            List[str]: List of important URLs that may not be in sitemap
        """
        # URLs importantes descobertas manualmente (não-ERP)
        important_urls = [
            # Senior Flow - Manual do Usuário
            "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/index.htm",
            
            # Senior Flow - Notas de Versão  
            "https://documentacao.senior.com.br/senior-flow/notas-da-versao/index.htm",
            
            # GED - URLs descobertas pelo usuário
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/index.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/conceito.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/checklist/checklist-digitalizacao.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/checklist/checklist-implantacao.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/utilizando-o-ged.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/coleta-de-assinatura.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/copia-pastas-arquivos.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/fluxo-de-assinatura.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/gerenciar-documentos.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/informacoes-apis.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/recursos.htm",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/permissoes.htm",
            
            # SIGN Studio
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/index.htm",
            
            # BPM
            "https://documentacao.senior.com.br/bpm/7.0.0/index.htm",
            
            # Senior Connect
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/senior-connect/index.htm",
            
            # ERP Senior X - Base
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/index.htm",
        ]
        
        # Adicionar URLs do ERP baseadas no mapeamento manual do usuário
        erp_urls = self._get_erp_urls_from_manual_mapping()
        important_urls.extend(erp_urls)
        
        logger.info(f"Added {len(important_urls)} manually discovered important URLs ({len(erp_urls)} from ERP mapping)")
        return important_urls
    
    def _get_erp_urls_from_manual_mapping(self) -> List[str]:
        """Get ERP URLs from manual mapping analysis.
        
        Based on user's comprehensive manual mapping of ERP documentation.
        These URLs represent the deep hierarchical structure that SPA discovery misses.
        
        Returns:
            List[str]: ERP URLs from manual mapping
        """
        # URLs do ERP baseadas no mapeamento manual completo do usuário
        # Estas URLs representam a estrutura hierárquica profunda que a descoberta SPA não consegue encontrar
        erp_base = "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/"
        
        # Fragmentos de URL extraídos do mapeamento manual (links_doc_erp.md)
        erp_fragments = [
            # Suprimentos
            "suprimentos/demandas/relatorios/reserva-estoque-pedido-venda.htm",
            "suprimentos/demandas/relatorios/reserva-estoque.htm",
            "suprimentos/recebimento/recebimento.htm",
            "suprimentos/recebimento/recebimento-eletronico.htm",
            "suprimentos/recebimento/nota-fiscal-entrada.htm",
            "suprimentos/recebimento/nota-importacao.htm",
            "suprimentos/recebimento/sugestao-valores-nota-fiscal-entrada.htm",
            "suprimentos/recebimento/integracao-nota-fiscal-entrada-via-api.htm",
            "suprimentos/recebimento/wms/conferencia-wms.htm",
            "suprimentos/recebimento/relatorio-nota-fiscal-entrada.htm",
            "suprimentos/estoque/estoque.htm",
            "suprimentos/estoque/listagem-movimentos.htm",
            "suprimentos/estoque/movimento-estoque.htm",
            "suprimentos/estoque/manutencao-lotes-series.htm",
            "suprimentos/estoque/fechamento.htm",
            "suprimentos/estoque/valorizacao.htm",
            "suprimentos/estoque/curva-abc.htm",
            "suprimentos/estoque/Consultas/saldo-estoque.htm",
            "suprimentos/estoque/Consultas/saldo-diario.htm",
            "suprimentos/estoque/Consultas/saldo-terceiros.htm",
            "suprimentos/estoque/Consultas/saldo-consolidado.htm",
            "suprimentos/estoque/requisicao.htm",
            "suprimentos/estoque/analise-de-reposicao.htm",
            "suprimentos/estoque/relatorios/movimentos.htm",
            "suprimentos/inventario/inventario.htm",
            
            # Finanças
            "financas/gestao-financas.htm",
            "financas/contas-receber/contas-receber.htm",
            "financas/contas-receber/titulos-contas-receber.htm",
            "financas/contas-receber/desconto-concedido.htm",
            "financas/contas-receber/cobranca-escritural.htm",
            "financas/contas-receber/cobranca-pix.htm",
            "financas/contas-receber/analise-de-credito.htm",
            "financas/contas-pagar/contas-pagar.htm",
            "financas/contas-pagar/titulos-contas-pagar.htm",
            "financas/contas-pagar/baixa-titulos.htm",
            "financas/contas-pagar/pagamento-eletronico.htm",
            "financas/contas-pagar/comissoes.htm",
            "financas/tesouraria/tesouraria.htm",
            "financas/tesouraria/movimentacao-conta.htm",
            "financas/tesouraria/transferencia-bancaria.htm",
            "financas/tesouraria/inclusao-titulos-receber.htm",
            "financas/tesouraria/inclusao-titulos-pagar.htm",
            "financas/tesouraria/credito-cliente.htm",
            "financas/tesouraria/devolucao-credito-cliente.htm",
            "financas/tesouraria/credito-fornecedor.htm",
            "financas/tesouraria/devolucao-credito-fornecedor.htm",
            "financas/tesouraria/conciliacao-bancaria.htm",
            "financas/tesouraria/relatorios.htm",
            "financas/tesouraria/relatorios/consolidado.htm",
            "financas/tesouraria/relatorios/diario.htm",
            "financas/tesouraria/relatorios/detalhado.htm",
            "financas/tesouraria/relatorios/conciliacao-bancaria.htm",
            "financas/tesouraria/relatorios/demonstrativo-financeiro.htm",
            "financas/plano-financeiro/fluxo-de-caixa/fluxo-de-caixa.htm",
            "financas/plano-financeiro/fluxo-de-caixa/carga-inicial.htm",
            "financas/plano-financeiro/fluxo-de-caixa/parametrizacoes.htm",
            "financas/plano-financeiro/fluxo-de-caixa/cenarios.htm",
            "financas/plano-financeiro/fluxo-de-caixa/distribuicoes.htm",
            "financas/plano-financeiro/fluxo-de-caixa/movimentacoes-diversas.htm",
            "financas/plano-financeiro/fluxo-de-caixa/percentuais.htm",
            "financas/plano-financeiro/composicao-do-saldo.htm",
            "financas/lote-financeiro.htm",
            
            # Banking
            "Banking/banking.htm",
            "Banking/Recebimento/boleto.htm",
            "Banking/Recebimento/pix.htm",
            "Banking/ativacao-parceiros/ativacao-esales.htm",
            "Banking/ativacao-parceiros/onboarding-btg.htm",
            "Banking/Pagamento/pagamento-boleto.htm",
            "Banking/Pagamento/pagamento-pix.htm",
            "Banking/servicos-financeiros/desconto-duplicatas.htm",
            "Banking/servicos-financeiros/antecipacao-cartao.htm",
            "Banking/tesouraria/gestao-de-caixa.htm",
            "Banking/tesouraria/calcbank.htm",
            
            # Controladoria
            "controladoria/gestao-controladoria.htm",
            "contabilidade-externa/movimento-contabilidade-externa.htm",
            "contabilidade-externa/bloco-0.htm",
            "contabilidade-externa/bloco-c.htm",
            "contabilidade-externa/bloco-d.htm",
            "contabilidade-externa/bloco-h.htm",
            "contabilidade-externa/bloco-k.htm",
            "controladoria/relatorio-retencoes.htm",
            "controladoria/compliance/compliance-fiscal.htm",
            "controladoria/compliance/monitoramento.htm",
            "controladoria/compliance/integracoes-documentos.htm",
            "controladoria/compliance/cadastros-manuais-web.htm",
            "controladoria/gestao-contabilidade/gestao-contabilidade.htm",
            "controladoria/gestao-contabilidade/integracao-contabil.htm",
            "controladoria/gestao-contabilidade/lancamento-contabil.htm",
            "controladoria/gestao-contabilidade/gestao-lotes-contabeis.htm",
            "controladoria/gestao-contabilidade/demonstrativos/demostrativos.htm",
            "controladoria/gestao-contabilidade/demonstrativos/relatorio-diario.htm",
            "controladoria/gestao-contabilidade/demonstrativos/balancete.htm",
            "controladoria/gestao-contabilidade/demonstrativos/dre.htm",
            "controladoria/gestao-contabilidade/demonstrativos/balanco-patrimonial.htm",
            "controladoria/gestao-contabilidade/demonstrativos/razao-contabil.htm",
            "controladoria/gestao-contabilidade/demonstrativos/razao-centro-custo.htm",
            "controladoria/gestao-contabilidade/demonstrativos/balancete-mensal.htm",
            "controladoria/gestao-contabilidade/demonstrativos/nota-explicativa.htm",
            "controladoria/gestao-contabilidade/demonstrativos/termo-abertura-encerramento.htm",
            
            # Industrial (Subsystems)
            "Subsystems/index/gestao-industrial/gestao-industrial.htm",
            "Subsystems/index/gestao-industrial/gestao-custos/custo-materiais.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/gestao-engenharia.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/engenharia-processo.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/cadastros-gerais.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/centro-recursos.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/recurso.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/estagio.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/processo-industrial.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/roteiro.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/sku.htm",
            "Subsystems/index/gestao-industrial/gestao-engenharia/parametro-engenharia.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/gestao-pcp.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/ordens-producao.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/parametros-pcp.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/cadastros.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/motivos-parada.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/operadores.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/funcao.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/calendario.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/turnos-de-producao.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/otif.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/montagem-de-carga.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/programacao-gantt.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/programacao-producao.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/rastreabilidade.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/plano-detalhado.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/alertas-pcp.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/ordem-separacao.htm",
            "Subsystems/index/gestao-industrial/gestao-pcp/ordem-devolucao.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/gestao-chao-fabrica.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/reporte-producao.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/apontamento-recurso.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/apontamento-estagio.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/apontamento-carga.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/parada-recursos.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/controle-lote-serie.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/apontamento-estoque.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/apontamento-integracao-wms.htm",
            "Subsystems/index/gestao-industrial/gestao-chao-fabrica/etiquetas.htm",
            "Subsystems/index/gestao-industrial/terceiros/gestao-terceiros.htm",
            "Subsystems/index/gestao-industrial/terceiros/remessa.htm",
            "Subsystems/index/gestao-industrial/terceiros/retorno.htm",
            "Subsystems/index/gestao-industrial/terceiros/prestacao-terceiros.htm",
            "Subsystems/index/gestao-industrial/gestao-mps/gestao-mps.htm",
            "Subsystems/index/gestao-industrial/gestao-mps/gerenciar-mps.htm",
            "Subsystems/index/gestao-industrial/gestao-mps/projetar-mps.htm",
            "Subsystems/index/gestao-industrial/gestao-mrp/planejamento-materiais.htm",
            "Subsystems/index/gestao-industrial/gestao-mrp/importacao-necessidade.htm",
            "Subsystems/index/gestao-industrial/gestao-mrp/calculo.htm",
            "Subsystems/index/gestao-industrial/gestao-mrp/parametros-mrp.htm",
            
            # Inteligência Tributária
            "inteligencia-tributaria/inteligencia-tributaria.htm",
            "inteligencia-tributaria/calculadora-reforma.htm",
            "inteligencia-tributaria/simulador-reforma.htm",
            
            # Custos
            "custos/gestao-custos.htm",
            "custos/custo-real/custo-real.htm",
            "custos/custo-real/cadastros/parametros-gerais.htm",
            "custos/custo-real/cadastros/transacoes-e-criterios.htm",
            "custos/custo-real/cadastros/periodos.htm",
            "custos/custo-real/cadastros/familia.htm",
            "custos/custo-real/cadastros/cadastro-de-taxas.htm",
            "custos/custo-real/processos/saldo-inicial-custos.htm",
            "custos/custo-real/processos/processamento-periodo.htm",
            "custos/custo-real/consultas/apontamentos-integrados.htm",
            "custos/custo-real/consultas/movimentos-integrados-processados.htm",
            "custos/custo-real/consultas/movimentos.htm",
            "custos/custo-real/consultas/saldo-por-produto.htm",
            "custos/custo-real/consultas/saldo-por-ordem.htm",
            "custos/custo-real/conferencias/transferencia-custos-suprimentos.htm",
            "custos/formacao-preco/formacao-preco.htm",
            "custos/formacao-preco/cadastros/formacao-familias.htm",
            "custos/formacao-preco/cadastros/markup.htm",
            "custos/formacao-preco/cadastros/fatores-markup.htm",
            "custos/formacao-preco/cadastros/custos-integrados.htm",
            "custos/formacao-preco/processos/processamento-markup.htm",
            "custos/formacao-preco/processos/integracao-tabela-preco.htm",
            "custos/formacao-preco/consultas/precos-formados.htm",
            "custos/custo-padrão/custo-padrao.htm",
            "custos/custo-padrão/cadastros/rubricas.htm",
            "custos/custo-padrão/cadastros/parametros-custeio.htm",
            "custos/custo-padrão/cadastros/familias-custo-padrao.htm",
            "custos/custo-padrão/cadastros/taxadores.htm",
            "custos/custo-padrão/cadastros/taxas.htm",
            "custos/custo-padrão/cadastros/regras-de-custeio.htm",
            "custos/custo-padrão/cadastros/conjunto-de-custo.htm",
            "custos/custo-padrão/cadastros/cenario-de-custo.htm",
            "custos/custo-padrão/processos/processamento-custo-padrao.htm",
            "custos/custo-padrão/consultas/valores-entrada.htm",
            "custos/custo-padrão/consultas/custo-produto.htm",
            "custos/custo-padrão/consultas/custo-por-explosao.htm",
            
            # Integrações
            "integracoes/wmsx/integracao-wmsx.htm",
            "integracoes/wmsx/recebimento-wmsx.htm",
            "integracoes/wmsx/integracao-recebimento-api.htm",
            "integracoes/wmsx/separacao-wmsx.htm",
            "integracoes/wmsx/integracao-separacao-api.htm",
            
            # Analytics
            "analytics/indicadores/indicadores-recebimento.htm",
            "analytics/indicadores/indicadores-estoque.htm",
            "analytics/indicadores/indicadores-gestao-financas.htm",
            "analytics/indicadores/indicadores-informacoes-fiscais.htm",
            "analytics/indicadores/indicadores-informacoes-contabeis.htm",
            "analytics/indicadores/indicadores-gestao-industrial.htm",
            "analytics/indicadores/indicadores-custos.htm",
            "analytics/indicadores/indicadores.htm",
            "analytics/opcao-analytics.htm",
            "analytics/visoes-dinamicas/visoes-dinamicas.htm",
            
            # Recursos
            "agendamentos/agendamentos.htm",
            "relatorios-customizados/relatorios-customizados.htm",
            
            # Outros
            "mercado/rateio/rateio.htm",
            "lgpd.htm",
        ]
        
        # Construir URLs completas
        erp_urls = [erp_base + "#" + fragment for fragment in erp_fragments]
        
        logger.info(f"Generated {len(erp_urls)} ERP URLs from manual mapping")
        return erp_urls
    
    async def discover_spa_urls(self) -> List[str]:
        """Discover URLs from SPAs using Playwright.
        
        Uses Playwright to load JavaScript SPAs and extract all .htm file references
        from the loaded content and navigation structures. Includes recursive discovery
        for hierarchical documentation structures.
        
        Returns:
            List[str]: List of discovered SPA URLs
        """
        logger.info("Starting intelligent SPA discovery")
        
        # Base URLs to crawl (SPAs)
        spa_base_urls = [
            "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/",
            "https://documentacao.senior.com.br/senior-flow/notas-da-versao/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/",
            "https://documentacao.senior.com.br/bpm/7.0.0/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/senior-connect/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/",
        ]
        
        all_discovered = []
        
        try:
            # Import Playwright (optional dependency)
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                for base_url in spa_base_urls:
                    try:
                        if "erp" in base_url:
                            # Use recursive discovery for ERP (hierarchical structure)
                            discovered = await self._discover_spa_urls_recursive(browser, base_url)
                        else:
                            # Use single-level discovery for other SPAs
                            discovered = await self._discover_spa_urls_single(browser, base_url)
                        
                        all_discovered.extend(discovered)
                        logger.info(f"Discovered {len(discovered)} URLs from {base_url}")
                    except Exception as e:
                        logger.warning(f"Failed to discover URLs from {base_url}: {e}")
                
                await browser.close()
        
        except ImportError:
            logger.warning("Playwright not available, skipping SPA discovery. Install with: pip install playwright")
            return []
        except Exception as e:
            logger.error(f"SPA discovery failed: {e}")
            return []
        
        # Remove duplicates and validate
        unique_urls = list(set(all_discovered))
        valid_urls = self._validate_discovered_urls(unique_urls)
        
        logger.info(f"SPA discovery completed: {len(unique_urls)} discovered, {len(valid_urls)} valid")
        return valid_urls
    
    async def _discover_spa_urls_single(self, browser, base_url: str) -> List[str]:
        """Discover URLs from a single SPA.
        
        Args:
            browser: Playwright browser instance
            base_url: Base URL of the SPA
            
        Returns:
            List[str]: Discovered URLs from this SPA
        """
        discovered = []
        
        page = await browser.new_page()
        
        try:
            # Navigate to SPA
            await page.goto(base_url, wait_until="networkidle", timeout=30000)
            
            # Wait for JavaScript to load content
            await page.wait_for_timeout(3000)
            
            # Method 1: Extract from page content
            content = await page.content()
            
            # Find all href patterns with .htm
            htm_patterns = [
                r'href=["\']([^"\']*\.htm[^"\']*)["\']',  # href="file.htm"
                r'#([^"\']*\.htm[^"\']*)',  # #path/file.htm
                r'([^"\'\s]*\.htm)',  # any .htm reference
            ]
            
            for pattern in htm_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Clean and resolve URL
                    if match.startswith('#'):
                        # Fragment URL
                        file_path = match[1:]  # Remove #
                        file_path = unquote(file_path)  # Decode %20 etc
                        full_url = urljoin(base_url, file_path)
                    elif match.startswith('http'):
                        # Absolute URL
                        full_url = match
                    else:
                        # Relative URL
                        full_url = urljoin(base_url, match)
                    
                    # Only include URLs under the base
                    if full_url.startswith(base_url) and full_url.endswith('.htm'):
                        discovered.append(full_url)
            
            # Method 2: Execute JavaScript to find navigation links
            try:
                js_links = await page.evaluate("""
                    () => {
                        const links = [];
                        
                        // Find all links
                        const anchors = document.querySelectorAll('a[href]');
                        anchors.forEach(a => {
                            const href = a.getAttribute('href');
                            if (href && href.includes('.htm')) {
                                links.push(href);
                            }
                        });
                        
                        // Find navigation data in JavaScript variables
                        const scripts = document.querySelectorAll('script');
                        scripts.forEach(script => {
                            const text = script.textContent || '';
                            
                            // Look for common patterns
                            const patterns = [
                                /["']([^"']*\\.htm[^"']*)["']/g,
                                /url:\\s*["']([^"']*\\.htm[^"']*)["']/g,
                                /path:\\s*["']([^"']*\\.htm[^"']*)["']/g,
                            ];
                            
                            patterns.forEach(pattern => {
                                let match;
                                while ((match = pattern.exec(text)) !== null) {
                                    links.push(match[1]);
                                }
                            });
                        });
                        
                        return [...new Set(links)]; // Remove duplicates
                    }
                """)
                
                # Process JavaScript-discovered links
                for link in js_links:
                    if link.startswith('#'):
                        file_path = link[1:]
                        file_path = unquote(file_path)
                        full_url = urljoin(base_url, file_path)
                    elif link.startswith('http'):
                        full_url = link
                    else:
                        full_url = urljoin(base_url, link)
                    
                    if full_url.startswith(base_url) and full_url.endswith('.htm'):
                        discovered.append(full_url)
            
            except Exception as e:
                logger.debug(f"JavaScript execution failed for {base_url}: {e}")
        
        finally:
            await page.close()
        
        # Remove duplicates
        return list(set(discovered))
    
    def _validate_discovered_urls(self, urls: List[str]) -> List[str]:
        """Validate that discovered URLs are accessible.
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            List[str]: List of valid URLs
        """
        if not urls:
            return []
        
        logger.info(f"Validating {len(urls)} discovered URLs")
        
        valid_urls = []
        
        for url in urls:
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    valid_urls.append(url)
            except Exception:
                # Skip invalid URLs silently
                pass
        
        logger.info(f"Validation completed: {len(valid_urls)}/{len(urls)} URLs are valid")
        return valid_urls
    
    async def _discover_spa_urls_recursive(self, browser, base_url: str, max_depth: int = 4) -> List[str]:
        """Recursively discover URLs from hierarchical SPAs like ERP with enhanced module-based discovery.
        
        Args:
            browser: Playwright browser instance
            base_url: Base URL of the SPA
            max_depth: Maximum recursion depth (default: 4 for deeper ERP structure)
            
        Returns:
            List[str]: All discovered URLs from recursive crawling
        """
        logger.info(f"Starting enhanced recursive discovery for {base_url} (max_depth={max_depth})")
        
        all_urls = set()
        
        # Enhanced ERP module mapping based on manual analysis
        erp_modules = {
            "suprimentos": ["demandas", "recebimento", "estoque", "inventario"],
            "financas": ["gestao-financas", "contas-receber", "contas-pagar", "tesouraria", "plano-financeiro"],
            "Banking": ["banking", "Recebimento", "Pagamento", "ativacao-parceiros", "servicos-financeiros", "tesouraria"],
            "controladoria": ["gestao-controladoria", "contabilidade-externa", "compliance", "gestao-contabilidade"],
            "Subsystems/index/gestao-industrial": ["gestao-industrial", "gestao-custos", "gestao-engenharia", "gestao-pcp", "gestao-chao-fabrica", "terceiros", "gestao-mps", "gestao-mrp"],
            "inteligencia-tributaria": ["inteligencia-tributaria", "calculadora-reforma"],
            "custos": ["gestao-custos", "custo-real", "formacao-preco", "custo-padrão"],
            "integracoes": ["wmsx"],
            "analytics": ["indicadores", "visoes-dinamicas"],
        }
        
        # Common subpages found in analysis
        common_subpages = ["cadastros", "processos", "consultas", "relatorios", "conferencias", "demonstrativos", "blocos"]
        
        # Systematically explore each module
        for module_path, submodules in erp_modules.items():
            logger.info(f"Exploring module: {module_path}")
            
            for submodule in submodules:
                # Try different URL patterns based on manual analysis
                patterns = [
                    f"#{module_path}/{submodule}.htm",
                    f"#{module_path}/{submodule}/{submodule}.htm",
                    f"#{submodule}/{submodule}.htm",
                ]
                
                for pattern in patterns:
                    try:
                        full_url = base_url + pattern
                        discovered = await self._explore_erp_url_pattern(browser, full_url, module_path, submodule, common_subpages)
                        all_urls.update(discovered)
                    except Exception as e:
                        logger.debug(f"Pattern {pattern} failed: {e}")
        
        # Also try the original recursive approach for any missed URLs
        try:
            original_urls = await self._original_recursive_discovery(browser, base_url, max_depth)
            all_urls.update(original_urls)
        except Exception as e:
            logger.warning(f"Original recursive discovery failed: {e}")
        
        result = list(all_urls)
        logger.info(f"Enhanced recursive discovery completed: {len(result)} total URLs found")
        return result
    
    async def _explore_erp_url_pattern(self, browser, base_url: str, module_path: str, submodule: str, common_subpages: List[str]) -> Set[str]:
        """Explore a specific ERP URL pattern in depth."""
        discovered_urls = set()
        
        page = await browser.new_page()
        
        try:
            # Navigate to the base pattern
            await page.goto(base_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Extract URLs from this page
            page_urls = await self._extract_erp_urls_from_page(page, base_url)
            discovered_urls.update(page_urls)
            
            # Explore common subpages
            for subpage in common_subpages:
                subpage_patterns = [
                    f"#{module_path}/{submodule}/{subpage}",
                    f"#{module_path}/{submodule}/{subpage}/{subpage}.htm",
                    f"#{submodule}/{subpage}",
                ]
                
                for subpage_pattern in subpage_patterns:
                    try:
                        subpage_url = base_url.split('#')[0] + subpage_pattern
                        await page.goto(subpage_url, wait_until="networkidle", timeout=10000)
                        await page.wait_for_timeout(1500)
                        
                        subpage_urls = await self._extract_erp_urls_from_page(page, subpage_url)
                        discovered_urls.update(subpage_urls)
                        
                    except Exception:
                        continue  # Skip failed subpages
        
        finally:
            await page.close()
        
        return discovered_urls
    
    async def _extract_erp_urls_from_page(self, page, current_url: str) -> Set[str]:
        """Enhanced URL extraction specifically for ERP pages."""
        urls = set()
        
        try:
            # Method 1: Extract from HTML content with ERP-specific patterns
            content = await page.content()
            
            # ERP-specific URL patterns
            erp_patterns = [
                r'href=["\']([^"\']*\.htm[^"\']*)["\']',
                r'#([^"\']*\.htm[^"\']*)',
                r'([^"\'\s]*\.htm)',
                # TocPath patterns from manual analysis
                r'TocPath[^"\']*["\']([^"\']*)["\']',
                # Fragment navigation patterns
                r'#([^"\'?]*(?:suprimentos|financas|Banking|controladoria|Subsystems|custos|inteligencia-tributaria)[^"\']*\.htm[^"\']*)',
            ]
            
            base_url = current_url.split('#')[0]
            
            for pattern in erp_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    clean_url = self._clean_erp_url(match, base_url)
                    if clean_url and self._is_valid_erp_url(clean_url):
                        urls.add(clean_url)
            
            # Method 2: Execute JavaScript to find dynamic navigation data
            js_urls = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // Look for navigation data in global variables
                    if (typeof window !== 'undefined') {
                        for (const key in window) {
                            try {
                                const value = window[key];
                                if (typeof value === 'object' && value !== null) {
                                    const str = JSON.stringify(value);
                                    // Look for ERP module patterns
                                    const erpMatches = str.match(/(suprimentos|financas|Banking|controladoria|Subsystems|custos|inteligencia-tributaria)[^"']*\\.htm/g);
                                    if (erpMatches) {
                                        erpMatches.forEach(match => urls.add(match));
                                    }
                                }
                            } catch (e) {
                                // Ignore serialization errors
                            }
                        }
                    }
                    
                    // Look for navigation menu items
                    document.querySelectorAll('a[href*=".htm"], [data-path*=".htm"], [onclick*=".htm"]').forEach(el => {
                        const href = el.getAttribute('href') || el.getAttribute('data-path') || el.getAttribute('onclick');
                        if (href && href.includes('.htm')) {
                            urls.add(href);
                        }
                    });
                    
                    return Array.from(urls);
                }
            """)
            
            for url in js_urls:
                clean_url = self._clean_erp_url(url, base_url)
                if clean_url and self._is_valid_erp_url(clean_url):
                    urls.add(clean_url)
                    
        except Exception as e:
            logger.debug(f"Error extracting URLs from {current_url}: {e}")
        
        return urls
    
    def _clean_erp_url(self, url: str, base_url: str) -> str:
        """Clean and normalize ERP URLs."""
        if not url:
            return ""
        
        # Remove JavaScript and other non-URL content
        url = re.sub(r'^[^#]*#', '#', url)  # Keep only fragment part if it starts with #
        
        if url.startswith('#'):
            return base_url + url
        elif url.startswith('http'):
            return url
        elif url.endswith('.htm'):
            return base_url + '#' + url
        else:
            return ""
    
    def _is_valid_erp_url(self, url: str) -> bool:
        """Check if URL is a valid ERP documentation URL."""
        if not url or not url.endswith('.htm'):
            return False
        
        # Must be ERP URL
        if 'seniorxplatform/manual-do-usuario/erp' not in url:
            return False
        
        # Must contain ERP module patterns
        erp_modules = ['suprimentos', 'financas', 'Banking', 'controladoria', 'Subsystems', 'custos', 'inteligencia-tributaria', 'analytics', 'integracoes']
        return any(module in url for module in erp_modules)
    
    async def _original_recursive_discovery(self, browser, base_url: str, max_depth: int) -> Set[str]:
        """Original recursive discovery method as fallback."""
        all_urls = set()
        visited_urls = set()
        urls_to_visit = [(base_url, 0)]
        
        while urls_to_visit:
            current_url, depth = urls_to_visit.pop(0)
            
            if current_url in visited_urls or depth > max_depth:
                continue
            
            visited_urls.add(current_url)
            
            try:
                page_urls = await self._discover_spa_urls_single(browser, current_url)
                
                for url in page_urls:
                    all_urls.add(url)
                    
                    if depth < max_depth and url not in visited_urls:
                        if self._is_navigation_url(url):
                            urls_to_visit.append((url, depth + 1))
                            
            except Exception as e:
                logger.debug(f"Failed to discover URLs from {current_url}: {e}")
        
        return all_urls
    
    def _is_navigation_url(self, url: str) -> bool:
        """Check if URL looks like a navigation/menu page that might contain more links.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL looks like a navigation page
        """
        # Navigation indicators in URL path
        nav_indicators = [
            'menu', 'index', 'home', 'gestao', 'cadastros',
            'configuracao', 'administracao', 'principal'
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in nav_indicators)
