#!/usr/bin/env python3
"""
Enhanced ERP Discovery Script

Este script implementa descoberta inteligente aprimorada para o ERP Senior X,
capaz de descobrir centenas de URLs específicas que não estão sendo encontradas
pelo sistema atual.

Baseado no mapeamento manual fornecido pelo usuário em links_doc_erp.md
"""

import asyncio
import re
import json
from typing import List, Set, Dict
from urllib.parse import urljoin, unquote, quote
import requests
from bs4 import BeautifulSoup

class EnhancedERPDiscovery:
    """Descoberta aprimorada para ERP Senior X com navegação hierárquica profunda."""
    
    def __init__(self):
        self.base_url = "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/"
        self.discovered_urls = set()
        self.visited_fragments = set()
        
        # Módulos principais do ERP baseados no mapeamento manual
        self.erp_modules = {
            "suprimentos": [
                "demandas", "recebimento", "estoque", "inventario"
            ],
            "financas": [
                "gestao-financas", "contas-receber", "contas-pagar", 
                "tesouraria", "plano-financeiro", "lote-financeiro"
            ],
            "Banking": [
                "banking", "Recebimento", "Pagamento", "ativacao-parceiros",
                "servicos-financeiros", "tesouraria"
            ],
            "controladoria": [
                "gestao-controladoria", "contabilidade-externa", "compliance",
                "gestao-contabilidade"
            ],
            "Subsystems/index/gestao-industrial": [
                "gestao-industrial", "gestao-custos", "gestao-engenharia",
                "gestao-pcp", "gestao-chao-fabrica", "terceiros",
                "gestao-mps", "gestao-mrp"
            ],
            "inteligencia-tributaria": [
                "inteligencia-tributaria", "calculadora-reforma"
            ],
            "custos": [
                "gestao-custos", "custo-real", "formacao-preco", "custo-padrão"
            ]
        }
        
        # Padrões de subpáginas comuns
        self.common_subpages = [
            "cadastros", "processos", "consultas", "relatorios", 
            "conferencias", "demonstrativos", "blocos", "parametros",
            "gestao", "operacional", "estrategico", "analytics"
        ]
    
    async def discover_all_erp_urls(self) -> List[str]:
        """Descobre todas as URLs do ERP usando múltiplas estratégias."""
        print("🔍 Iniciando descoberta aprimorada do ERP Senior X...")
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                
                # Estratégia 1: Descoberta por módulos conhecidos
                await self._discover_by_modules(browser)
                
                # Estratégia 2: Descoberta por navegação JavaScript
                await self._discover_by_javascript_navigation(browser)
                
                # Estratégia 3: Descoberta por análise de conteúdo
                await self._discover_by_content_analysis(browser)
                
                await browser.close()
        
        except ImportError:
            print("⚠️ Playwright não disponível, usando descoberta alternativa...")
            await self._discover_alternative()
        
        # Validar URLs descobertas
        valid_urls = self._validate_urls(list(self.discovered_urls))
        
        print(f"✅ Descoberta concluída: {len(valid_urls)} URLs válidas encontradas")
        return valid_urls
    
    async def _discover_by_modules(self, browser):
        """Descobre URLs navegando sistematicamente por módulos conhecidos."""
        print("📂 Descobrindo por módulos conhecidos...")
        
        page = await browser.new_page()
        
        try:
            # Navegar para página principal do ERP
            await page.goto(self.base_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Para cada módulo principal
            for module_path, submodules in self.erp_modules.items():
                print(f"  🔍 Explorando módulo: {module_path}")
                
                # Tentar navegar para cada submódulo
                for submodule in submodules:
                    await self._explore_submodule(page, module_path, submodule)
                    
        finally:
            await page.close()
    
    async def _explore_submodule(self, page, module_path: str, submodule: str):
        """Explora um submódulo específico em profundidade."""
        
        # Construir fragmentos de URL possíveis
        possible_fragments = [
            f"#{module_path}/{submodule}.htm",
            f"#{module_path}/{submodule}/{submodule}.htm",
            f"#{submodule}/{submodule}.htm",
        ]
        
        for fragment in possible_fragments:
            try:
                full_url = self.base_url + fragment
                
                if fragment in self.visited_fragments:
                    continue
                    
                self.visited_fragments.add(fragment)
                
                # Navegar para o fragmento
                await page.goto(full_url, wait_until="networkidle", timeout=10000)
                await page.wait_for_timeout(2000)
                
                # Extrair URLs da página atual
                urls = await self._extract_urls_from_page(page)
                self.discovered_urls.update(urls)
                
                # Procurar por subpáginas
                await self._discover_subpages(page, module_path, submodule)
                
            except Exception as e:
                print(f"    ⚠️ Erro ao explorar {fragment}: {e}")
    
    async def _discover_subpages(self, page, module_path: str, submodule: str):
        """Descobre subpáginas dentro de um módulo."""
        
        for subpage in self.common_subpages:
            try:
                # Tentar diferentes padrões de subpáginas
                patterns = [
                    f"#{module_path}/{submodule}/{subpage}",
                    f"#{module_path}/{submodule}/{subpage}/{subpage}.htm",
                    f"#{submodule}/{subpage}",
                ]
                
                for pattern in patterns:
                    if pattern in self.visited_fragments:
                        continue
                        
                    self.visited_fragments.add(pattern)
                    full_url = self.base_url + pattern
                    
                    await page.goto(full_url, wait_until="networkidle", timeout=8000)
                    await page.wait_for_timeout(1500)
                    
                    urls = await self._extract_urls_from_page(page)
                    self.discovered_urls.update(urls)
                    
            except Exception:
                continue  # Silenciosamente continuar se a subpágina não existir
    
    async def _extract_urls_from_page(self, page) -> Set[str]:
        """Extrai todas as URLs .htm da página atual."""
        urls = set()
        
        try:
            # Método 1: Extrair do conteúdo HTML
            content = await page.content()
            
            # Padrões para encontrar URLs .htm
            patterns = [
                r'href=["\']([^"\']*\.htm[^"\']*)["\']',
                r'#([^"\']*\.htm[^"\']*)',
                r'([^"\'\s]*\.htm)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match.startswith('#'):
                        clean_url = self.base_url + match
                    elif match.startswith('http'):
                        clean_url = match
                    else:
                        clean_url = urljoin(self.base_url, match)
                    
                    if clean_url.endswith('.htm') and 'erp' in clean_url:
                        urls.add(clean_url)
            
            # Método 2: Executar JavaScript para encontrar links dinâmicos
            js_urls = await page.evaluate("""
                () => {
                    const urls = new Set();
                    
                    // Procurar em todos os links
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href');
                        if (href && href.includes('.htm')) {
                            urls.add(href);
                        }
                    });
                    
                    // Procurar em scripts por padrões de URL
                    document.querySelectorAll('script').forEach(script => {
                        const text = script.textContent || '';
                        const matches = text.match(/["']([^"']*\\.htm[^"']*)["']/g);
                        if (matches) {
                            matches.forEach(match => {
                                const url = match.replace(/["']/g, '');
                                urls.add(url);
                            });
                        }
                    });
                    
                    // Procurar em dados de navegação
                    if (window.navigation || window.router) {
                        // Tentar extrair rotas do sistema de navegação
                    }
                    
                    return Array.from(urls);
                }
            """)
            
            for url in js_urls:
                if url.startswith('#'):
                    clean_url = self.base_url + url
                elif url.startswith('http'):
                    clean_url = url
                else:
                    clean_url = urljoin(self.base_url, url)
                
                if clean_url.endswith('.htm') and 'erp' in clean_url:
                    urls.add(clean_url)
                    
        except Exception as e:
            print(f"    ⚠️ Erro ao extrair URLs: {e}")
        
        return urls
    
    async def _discover_by_javascript_navigation(self, browser):
        """Descobre URLs analisando o sistema de navegação JavaScript."""
        print("🔧 Descobrindo via navegação JavaScript...")
        
        page = await browser.new_page()
        
        try:
            await page.goto(self.base_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
            
            # Tentar extrair dados de navegação do JavaScript
            nav_data = await page.evaluate("""
                () => {
                    const data = {
                        routes: [],
                        menuItems: [],
                        tocPaths: []
                    };
                    
                    // Procurar por dados de rota em variáveis globais
                    if (typeof window !== 'undefined') {
                        for (const key in window) {
                            try {
                                const value = window[key];
                                if (typeof value === 'object' && value !== null) {
                                    const str = JSON.stringify(value);
                                    if (str.includes('.htm')) {
                                        const matches = str.match(/[^"']*\\.htm[^"']*/g);
                                        if (matches) {
                                            data.routes.push(...matches);
                                        }
                                    }
                                }
                            } catch (e) {
                                // Ignorar erros de serialização
                            }
                        }
                    }
                    
                    // Procurar em elementos de menu
                    document.querySelectorAll('[data-path], [data-route], [data-url]').forEach(el => {
                        const path = el.getAttribute('data-path') || 
                                   el.getAttribute('data-route') || 
                                   el.getAttribute('data-url');
                        if (path && path.includes('.htm')) {
                            data.menuItems.push(path);
                        }
                    });
                    
                    // Procurar por TocPath patterns
                    const tocMatches = document.body.innerHTML.match(/TocPath[^"']*["'][^"']*["']/g);
                    if (tocMatches) {
                        data.tocPaths.push(...tocMatches);
                    }
                    
                    return data;
                }
            """)
            
            # Processar dados descobertos
            all_paths = nav_data['routes'] + nav_data['menuItems']
            for path in all_paths:
                if path.endswith('.htm'):
                    if path.startswith('#'):
                        full_url = self.base_url + path
                    else:
                        full_url = urljoin(self.base_url, path)
                    
                    self.discovered_urls.add(full_url)
                    
        finally:
            await page.close()
    
    async def _discover_by_content_analysis(self, browser):
        """Descobre URLs analisando o conteúdo das páginas já descobertas."""
        print("📄 Descobrindo via análise de conteúdo...")
        
        # Usar URLs já descobertas como ponto de partida
        current_urls = list(self.discovered_urls)
        
        page = await browser.new_page()
        
        try:
            for url in current_urls[:50]:  # Limitar para evitar timeout
                try:
                    await page.goto(url, wait_until="networkidle", timeout=10000)
                    await page.wait_for_timeout(1000)
                    
                    # Extrair mais URLs desta página
                    new_urls = await self._extract_urls_from_page(page)
                    self.discovered_urls.update(new_urls)
                    
                except Exception:
                    continue
                    
        finally:
            await page.close()
    
    async def _discover_alternative(self):
        """Descoberta alternativa sem Playwright usando requests."""
        print("🌐 Usando descoberta alternativa com requests...")
        
        # Usar o mapeamento manual como base
        manual_patterns = [
            "suprimentos/demandas/relatorios/reserva-estoque-pedido-venda.htm",
            "suprimentos/demandas/relatorios/reserva-estoque.htm",
            "suprimentos/recebimento/recebimento.htm",
            "suprimentos/estoque/estoque.htm",
            "financas/contas-receber/contas-receber.htm",
            "financas/contas-pagar/contas-pagar.htm",
            "financas/tesouraria/tesouraria.htm",
            "controladoria/gestao-controladoria.htm",
            "custos/gestao-custos.htm",
            "inteligencia-tributaria/inteligencia-tributaria.htm",
        ]
        
        for pattern in manual_patterns:
            full_url = f"{self.base_url}#{pattern}"
            self.discovered_urls.add(full_url)
    
    def _validate_urls(self, urls: List[str]) -> List[str]:
        """Valida que as URLs descobertas são acessíveis."""
        print(f"✅ Validando {len(urls)} URLs descobertas...")
        
        valid_urls = []
        
        for url in urls[:100]:  # Limitar validação para evitar timeout
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    valid_urls.append(url)
            except Exception:
                continue
        
        print(f"✅ {len(valid_urls)} URLs válidas confirmadas")
        return valid_urls

async def main():
    """Função principal para testar a descoberta aprimorada."""
    discovery = EnhancedERPDiscovery()
    urls = await discovery.discover_all_erp_urls()
    
    print(f"\n📊 RESULTADOS:")
    print(f"Total de URLs descobertas: {len(urls)}")
    
    # Agrupar por módulo
    modules = {}
    for url in urls:
        if '#suprimentos' in url:
            modules.setdefault('Suprimentos', []).append(url)
        elif '#financas' in url:
            modules.setdefault('Finanças', []).append(url)
        elif '#controladoria' in url:
            modules.setdefault('Controladoria', []).append(url)
        elif '#custos' in url:
            modules.setdefault('Custos', []).append(url)
        elif '#industrial' in url or '#Subsystems' in url:
            modules.setdefault('Industrial', []).append(url)
        elif '#inteligencia-tributaria' in url:
            modules.setdefault('Inteligência Tributária', []).append(url)
        elif '#Banking' in url:
            modules.setdefault('Banking', []).append(url)
        else:
            modules.setdefault('Outros', []).append(url)
    
    for module, module_urls in modules.items():
        print(f"  {module}: {len(module_urls)} URLs")
    
    # Salvar resultados
    with open('erp_discovered_urls.json', 'w', encoding='utf-8') as f:
        json.dump({
            'total_urls': len(urls),
            'urls_by_module': modules,
            'all_urls': urls
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Resultados salvos em 'erp_discovered_urls.json'")
    
    return urls

if __name__ == "__main__":
    asyncio.run(main())