"""Group assignment service — block randomization for 1:1:1 allocation."""
import random
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, ExperimentGroup
from app.models.system_config import SystemConfig


async def assign_group(db: AsyncSession, user: User) -> ExperimentGroup:
    """
    Block randomization: assign user to H / SOA / MOA with 1:1:1 ratio.
    Uses block size of 6 (2 complete sets of 3 groups).
    """
    # Count existing assignments per group
    result = await db.execute(
        select(User.group, func.count(User.id))
        .where(User.group.isnot(None))
        .group_by(User.group)
    )
    counts = {row[0]: row[1] for row in result.all()}

    h_count = counts.get(ExperimentGroup.H, 0)
    soa_count = counts.get(ExperimentGroup.SOA, 0)
    moa_count = counts.get(ExperimentGroup.MOA, 0)

    # Get target sample size
    target_result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "target_sample_size")
    )
    config = target_result.scalar_one_or_none()
    target = int(config.value) if config else 100
    per_group = target // 3

    # Check if any group is full
    groups_with_capacity = []
    if h_count < per_group:
        groups_with_capacity.append(ExperimentGroup.H)
    if soa_count < per_group:
        groups_with_capacity.append(ExperimentGroup.SOA)
    if moa_count < per_group:
        groups_with_capacity.append(ExperimentGroup.MOA)

    if not groups_with_capacity:
        # All groups full — default to least populated
        min_count = min(h_count, soa_count, moa_count)
        if h_count == min_count:
            return ExperimentGroup.H
        elif soa_count == min_count:
            return ExperimentGroup.SOA
        else:
            return ExperimentGroup.MOA

    # Block randomization: find the group with the fewest members
    # among groups with capacity, then randomize among ties
    min_count_in_capacity = min(
        counts.get(g, 0) for g in groups_with_capacity
    )
    least_populated = [
        g for g in groups_with_capacity
        if counts.get(g, 0) == min_count_in_capacity
    ]

    return random.choice(least_populated)
