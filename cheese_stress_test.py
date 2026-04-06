#!/usr/bin/env python3
"""
Cheese Stress Test Runner - Demonstrates the three stress test modes.

This script sets up WizBots with different test modes to stress-test
the cheese item system, inventory mechanics, and entity spawning.

Usage:
    python cheese_stress_test.py

The three stress test modes:
1. cheese_multiply_test: Spawn cheese until inventory full, then use each one
2. cheese_replicate_test: Spawn cheese one-at-a-time until full, then delete all except one
3. exploration (default): Random movement with occasional cheese interactions
"""

from pyrogue_engine.core.ecs import Registry
from pyrogue_engine.core.events import EventBus
from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
from wiz_bot import WizBotFactory


def setup_stress_test_bots():
    """
    Set up WizBots for stress testing.

    In headless_server.py run_server(), use this pattern:
    """
    registry = Registry()
    event_bus = EventBus()

    # Initialize WizBot AI system
    wiz_bot_ai = WizBotAI(registry, event_bus, config=None)
    wiz_bot_factory = WizBotFactory()

    # Scenario 1: Single bot with cheese_multiply_test
    print("\n=== STRESS TEST 1: CHEESE MULTIPLY TEST ===")
    bot1_id = wiz_bot_factory.spawn(registry, x=10, y=10, test_mode="cheese_multiply_test")
    wiz_bot_ai.register_wiz_bot(bot1_id)
    print(f"Bot {bot1_id}: Will spawn cheese until inventory full (10 items), then use each one")

    # Scenario 2: Single bot with cheese_replicate_test
    print("\n=== STRESS TEST 2: CHEESE REPLICATE TEST ===")
    bot2_id = wiz_bot_factory.spawn(registry, x=20, y=10, test_mode="cheese_replicate_test")
    wiz_bot_ai.register_wiz_bot(bot2_id)
    print(f"Bot {bot2_id}: Will spawn cheese one-at-a-time until full (10 items), then delete all except one")

    # Scenario 3: Multiple bots in exploration mode (control group)
    print("\n=== CONTROL GROUP: EXPLORATION MODE ===")
    for i in range(2):
        bot_id = wiz_bot_factory.spawn(registry, x=30 + i*10, y=10, test_mode="exploration")
        wiz_bot_ai.register_wiz_bot(bot_id)
        print(f"Bot {bot_id}: Random exploration with occasional cheese interactions")

    return registry, event_bus, wiz_bot_ai


def demonstrate_stress_test_flow():
    """Show what happens during a stress test."""
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║          CHEESE STRESS TEST - EXPECTED BEHAVIOR                ║
    ╚════════════════════════════════════════════════════════════════╝

    PHASE 1: CHEESE MULTIPLY TEST (Bot 1)
    ─────────────────────────────────────
    Frame  1: [WizBotAI] Bot 1 spawned cheese 1001, inventory 1/10
    Frame  3: [WizBotAI] Bot 1 spawned cheese 1002, inventory 2/10
    Frame  5: [WizBotAI] Bot 1 spawned cheese 1003, inventory 3/10
    ...
    Frame 19: [WizBotAI] Bot 1 spawned cheese 1010, inventory 10/10
    Frame 20: [WizBotAI] Bot 1 used cheese 1001, 9 remaining
    Frame 21: [WizBotAI] Bot 1 used cheese 1002, 8 remaining
    ...
    Frame 29: [WizBotAI] Bot 1 used cheese 1010, 0 remaining

    ✓ Tests: Item spawning, inventory tracking, item.used event

    PHASE 2: CHEESE REPLICATE TEST (Bot 2)
    ──────────────────────────────────────
    Frame  1: [WizBotAI] Bot 2 spawned cheese 2001, inventory 1/10
    Frame  2: [WizBotAI] Bot 2 spawned cheese 2002, inventory 2/10
    Frame  3: [WizBotAI] Bot 2 spawned cheese 2003, inventory 3/10
    ...
    Frame 10: [WizBotAI] Bot 2 spawned cheese 2010, inventory 10/10
    Frame 11: [WizBotAI] Bot 2 deleted cheese 2002, 9 remaining
    Frame 12: [WizBotAI] Bot 2 deleted cheese 2003, 8 remaining
    ...
    Frame 19: [WizBotAI] Bot 2 deleted cheese 2010, 1 remaining

    ✓ Tests: Entity spawning rate, entity deletion, generation limits

    PHASE 3: GENERATION LIMITING
    ───────────────────────────
    When a cheese is damaged (durability < 30%):
    [CheeseSystem] Cheese 1005 splitting! (durability 28 < 30, generation 0/3)
    [CheeseSystem] Spawned child cheese 1011 at (10, 9)
    [CheeseSystem] Spawned child cheese 1012 at (12, 11)
    [CheeseSystem] Spawned child cheese 1013 at (11, 10)

    Child cheeses (generation 1) can split into generation 2.
    Generation 2 can split into generation 3.
    Generation 3+ CANNOT split (max_generations=3).

    ✓ Tests: Prevents exponential growth (1→3→9→27 capped at 9)

    MONITORING METRICS
    ──────────────────
    Every 60 frames (3 seconds at 20 Hz), each bot logs:

    [WizBotAI] Bot 1 | Frame    60 | Mode cheese_multiply_test  | Entities 1050 | Stats: {'spawn_x': 10, 'spawn_y': 10, 'cheese_spawned': 10, 'cheese_used': 10}
    [WizBotAI] Bot 2 | Frame    60 | Mode cheese_replicate_test | Entities 1010 | Stats: {'spawn_x': 20, 'spawn_y': 10, 'cheese_spawned': 10, 'cheese_deleted': 9}

    Track these stats to detect:
    - Excessive entity growth (should plateau)
    - Test completion (all cheese used/deleted)
    - Any system crashes or freezes

    STRESS TEST SUCCESS CRITERIA
    ────────────────────────────
    ✓ No server crashes after 1000+ frames
    ✓ Entity count stabilizes (doesn't keep growing)
    ✓ Both test modes complete successfully
    ✓ Generation limits prevent exponential growth
    ✓ Replication to all clients happens smoothly
    ✓ No memory leaks (check Python memory usage)
    """)


if __name__ == "__main__":
    print("Cheese Stress Test Setup\n")
    demonstrate_stress_test_flow()

    print("\n" + "="*80)
    print("To run the stress tests in headless_server.py:")
    print("="*80)
    print("""
    In run_server() in headless_server.py, add after WizBotAI initialization:

    from cheese_stress_test import setup_stress_test_bots

    # Setup stress test bots
    # (Note: This would need to be integrated into the async run_server)
    # For now, use the pattern shown below:

    # Initialize WizBot AI system
    from pyrogue_engine.systems.rpg.wiz_bot_ai import WizBotAI
    from wiz_bot import WizBotFactory

    wiz_bot_ai = WizBotAI(registry, event_bus, config)
    wiz_bot_factory = WizBotFactory()

    # Spawn bot with cheese_multiply_test
    bot1 = wiz_bot_factory.spawn(registry, x=10, y=10, test_mode="cheese_multiply_test")
    wiz_bot_ai.register_wiz_bot(bot1)

    # Spawn bot with cheese_replicate_test
    bot2 = wiz_bot_factory.spawn(registry, x=20, y=10, test_mode="cheese_replicate_test")
    wiz_bot_ai.register_wiz_bot(bot2)

    # Spawn exploration bots as control group
    for i in range(2):
        bot = wiz_bot_factory.spawn(registry, x=30+i*10, y=10, test_mode="exploration")
        wiz_bot_ai.register_wiz_bot(bot)
    """)
