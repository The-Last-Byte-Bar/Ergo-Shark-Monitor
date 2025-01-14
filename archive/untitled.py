
# Usage example
async def setup_analytics():
    service = AnalyticsService()
    
    # Register metrics
    service.register_metric(FlowMetrics())
    service.register_metric(TokenMetrics())
    
    # Register prompt constructors
    service.register_prompt_constructor(StandardPromptConstructor())
    
    return service

# In LLMService
class LLMService:
    def __init__(self, explorer_client, llm_api_key: str):
        self.explorer_client = explorer_client
        self.llm_api_key = llm_api_key
        self.analytics = None
        
    async def init_session(self):
        self.analytics = await setup_analytics()
        
    async def process_query(self, query: str, address: str, days_back: int = 30) -> str:
        context_data = await self.gather_context_data(address, days_back)
        
        # Use analytics service
        analysis = await self.analytics.analyze(
            query,
            context_data.get('recent_transactions', []),
            context_data.get('current_balance', {})
        )
        
        response = await self.get_llm_response(analysis['prompt'])
        return response