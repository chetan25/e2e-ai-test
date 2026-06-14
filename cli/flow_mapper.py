"""
Phase 1: Dynamic UI crawling via Playwright
Maps user interactions and discovers flow sequences.
"""
import json
import asyncio
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass, asdict, field
from playwright.async_api import async_playwright, Page, BrowserContext, Response
import logging

logger = logging.getLogger(__name__)


@dataclass
class InteractionStep:
    action: str  # "navigate", "click", "fill", "wait"
    selector: str = ""
    data_testid: str = ""
    value: str = ""
    url: str = ""


@dataclass
class DiscoveredFlow:
    id: str
    name: str
    steps: List[InteractionStep]
    mocked_apis: List[Dict[str, Any]]


class PlaywrightUIMapper:
    """
    Maps user flows via Playwright browser automation.
    Discovers clickable elements, records interactions, and builds flow sequences.
    """
    
    def __init__(self, app_url: str, entry_point: str = "/"):
        self.app_url = app_url
        self.entry_point = entry_point
        self.flows: List[DiscoveredFlow] = []
        self.visited_urls: Set[str] = set()
        self.intercepted_apis: List[Dict[str, Any]] = []
        self.current_path: List[InteractionStep] = []

    async def crawl_and_discover_flows(self, max_pages: int = 10) -> List[DiscoveredFlow]:
        """
        Main entry point: Start from entry_point, crawl UI, discover flows.
        
        Uses Playwright to:
        1. Navigate to entry_point
        2. Identify clickable elements with data-testid selectors
        3. Record interactions
        4. Map out user journeys
        5. Detect mocked API calls
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Setup network interception
                await self._setup_network_interception(page)
                
                # Start crawling from entry point
                await self._crawl_page(page, context, max_pages=max_pages)
                
                await context.close()
                await browser.close()
        except Exception as e:
            logger.error(f"Error during crawl: {e}")
        
        return self.flows

    async def _setup_network_interception(self, page: Page) -> None:
        """Setup network interception to detect API calls."""
        async def capture_response(response: Response) -> None:
            try:
                url = response.url
                method = response.request.method
                resource_type = response.request.resource_type
                
                # Capture API calls and data fetches (exclude document, stylesheet, images, fonts, media)
                if resource_type in ["xhr", "fetch"] or "/api/" in url:
                    status = response.status
                    
                    try:
                        body = await response.json()
                    except:
                        try:
                            body = await response.text()
                        except:
                            body = None
                    
                    api_call = {
                        "url": url,
                        "method": method,
                        "status": status,
                        "response": body if isinstance(body, dict) else {"data": body} if body else {}
                    }
                    
                    # Avoid duplicates
                    if api_call not in self.intercepted_apis:
                        self.intercepted_apis.append(api_call)
            except Exception as e:
                logger.debug(f"Error capturing response: {e}")
        
        page.on("response", capture_response)

    async def _crawl_page(self, page: Page, context: BrowserContext, max_pages: int) -> None:
        """Crawl a page and discover clickable elements."""
        full_url = self.app_url + self.entry_point
        
        try:
            await page.goto(full_url, wait_until="networkidle", timeout=10000)
            self.visited_urls.add(full_url)
            
            # Start exploration from main page
            self.current_path = [
                InteractionStep(action="navigate", url=full_url)
            ]
            
            # Discover clickable elements
            clickables = await self._discover_clickable_elements(page)
            
            if clickables:
                # Create a flow for the discovered interactions
                flow = self._extract_flow_from_path(clickables[:5])  # Limit to 5 clicks per flow
                if flow.steps:
                    self.flows.append(flow)
        except Exception as e:
            logger.error(f"Error crawling page: {e}")

    async def _discover_clickable_elements(self, page: Page) -> List[InteractionStep]:
        """Discover all clickable elements with data-testid selectors."""
        clickables = []
        
        try:
            # Find all elements with data-testid attribute
            elements = await page.query_selector_all("[data-testid]")
            
            for i, element in enumerate(elements[:10]):  # Limit to 10 elements
                try:
                    data_testid = await element.get_attribute("data-testid")
                    tag = await element.evaluate("e => e.tagName")
                    
                    # Check if element is clickable (button, link, or has click handler)
                    is_clickable = tag in ["BUTTON", "A", "INPUT"] or \
                        await element.evaluate("e => e.onclick !== null || window.getComputedStyle(e).cursor === 'pointer'")
                    
                    if is_clickable and data_testid:
                        selector = f"[data-testid='{data_testid}']"
                        clickables.append(
                            InteractionStep(
                                action="click",
                                selector=selector,
                                data_testid=data_testid
                            )
                        )
                except Exception as e:
                    logger.debug(f"Error processing element {i}: {e}")
        except Exception as e:
            logger.error(f"Error discovering clickable elements: {e}")
        
        return clickables

    def _extract_flow_from_path(self, clickables: List[InteractionStep]) -> DiscoveredFlow:
        """Extract a user flow from a recorded interaction path."""
        steps = self.current_path.copy()
        steps.extend(clickables)
        
        # Create unique flow ID
        flow_id = f"flow_{len(self.flows) + 1}"
        flow_name = f"Discovered flow: {' -> '.join(s.data_testid or s.action for s in clickables[:3])}"
        
        return DiscoveredFlow(
            id=flow_id,
            name=flow_name,
            steps=steps,
            mocked_apis=self._detect_external_api_calls()
        )

    def _detect_external_api_calls(self) -> List[Dict[str, Any]]:
        """Detect external API calls to mock."""
        return self.intercepted_apis


async def map_ui_flows(app_url: str, static_analysis: Dict[str, Any]) -> List[DiscoveredFlow]:
    """
    Main entry: use Playwright to discover flows.
    """
    mapper = PlaywrightUIMapper(app_url)
    flows = await mapper.crawl_and_discover_flows()
    return flows
