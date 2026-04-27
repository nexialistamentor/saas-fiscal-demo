import asyncio

from app.agents.agent_scheduler import AgentScheduler


async def main():
    scheduler = AgentScheduler()
    await scheduler.iniciar_loop(intervalo_segundos=30)


if __name__ == "__main__":
    asyncio.run(main())
