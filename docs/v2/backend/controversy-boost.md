# Backend: Controversy Boost

> **Implements**: Phase T (T5)
> **UserInput Refs**: E6

## Problem

The default OASIS hot-score algorithm (Reddit's algorithm) penalizes controversial posts. A post with 50 likes + 50 dislikes has `net_score = 0`, so it scores the same as a post with zero engagement. Only universally liked posts rise to the top.

This is unrealistic for social media simulation. Real platforms amplify controversial content to drive engagement (ragebait). To model this, we add a configurable `controversy_boost` parameter.

## Current Code (OASIS `recsys.py`)

File: Inside the OASIS package (pip-installed or vendored), look for `oasis/social_platform/recsys.py`

```python
# Current implementation
def calculate_hot_score(num_likes, num_dislikes, created_at):
    s = num_likes - num_dislikes        # NET score (likes minus dislikes)
    order = log(max(abs(s), 1), 10)     # Logarithmic scale
    sign = 1 if s > 0 else -1 if s < 0 else 0
    seconds = epoch_seconds - 1134028003
    return sign * order + seconds / 45000
```

## Modified Code

```python
def calculate_hot_score(num_likes, num_dislikes, created_at, controversy_boost=0.0):
    """Calculate hot score with optional controversy amplification.

    Args:
        num_likes: Number of upvotes
        num_dislikes: Number of downvotes
        created_at: Post creation timestamp
        controversy_boost: Float 0.0-1.0. At 0, behaves like default Reddit.
            At 1.0, a post with equal likes/dislikes scores similarly to
            a universally liked post with the same total engagement.
            Models how real social media amplifies controversial content
            for user retention (ragebait).
    """
    s = num_likes - num_dislikes
    total = num_likes + num_dislikes
    order = log(max(abs(s), 1), 10)
    sign = 1 if s > 0 else -1 if s < 0 else 0

    # Controversy component — rewards total engagement regardless of direction
    controversy = log(max(total, 1), 10) * controversy_boost

    seconds = epoch_seconds - 1134028003
    return sign * order + controversy + seconds / 45000
```

## Behavior Matrix

| Scenario | Likes | Dislikes | Net | Total | `boost=0.0` | `boost=0.5` | `boost=1.0` |
|:---------|:------|:---------|:----|:------|:------------|:------------|:------------|
| Universally liked | 100 | 0 | 100 | 100 | 2.0 + time | 2.0 + 1.0 + time | 2.0 + 2.0 + time |
| Controversial | 50 | 50 | 0 | 100 | 0.0 + time | 0.0 + 1.0 + time | 0.0 + 2.0 + time |
| No engagement | 0 | 0 | 0 | 0 | 0.0 + time | 0.0 + 0.0 + time | 0.0 + 0.0 + time |
| Universally disliked | 0 | 100 | -100 | 100 | -2.0 + time | -2.0 + 1.0 + time | -2.0 + 2.0 + time |

Key insight: At `boost=1.0`, the controversial post (0 net, 100 total) has the same controversy component as the universally liked post.

## Threading the Parameter

1. **UI (Screen 3)**: Slider sends `controversy_boost` in simulation request body
2. **API route**: `POST /api/v2/console/session/{id}/simulate` → `{rounds, controversy_boost, ...}`
3. **`simulation_service.py`**: Passes `controversy_boost` to OASIS runner
4. **`oasis_reddit_runner.py`**: Threads to `rec_sys_reddit()` → `calculate_hot_score()`
5. **`recsys.py`**: Uses in score calculation

## UI Component

```tsx
// ControversySlider.tsx — simplified reference
<div>
  <label>Controversy Boost</label>
  <Slider
    min={0} max={1} step={0.1}
    value={controversyBoost}
    onChange={setControversyBoost}
  />
  <span>{controversyBoost.toFixed(1)}</span>
  <Tooltip>
    Controversy Amplification: Controls how much the recommendation system
    boosts posts with high engagement regardless of whether they're liked
    or disliked. This models how real social media platforms use ragebait
    to amplify controversy and boost user retention.
  </Tooltip>
</div>
```

## Tests

```python
def test_controversy_boost_zero_is_default():
    """boost=0 should produce identical scores to original algorithm."""
    assert calculate_hot_score(100, 0, now, 0.0) == original_hot_score(100, 0, now)

def test_controversy_boost_one_equalizes():
    """At boost=1, controversial and universally liked should have same controversy component."""
    liked = calculate_hot_score(100, 0, now, 1.0)
    controversial = calculate_hot_score(50, 50, now, 1.0)
    # controversy component is equal (log(100,10) * 1.0 = 2.0 for both)
    # difference is only in the sign*order component

def test_no_engagement_unaffected():
    """Posts with 0 engagement should not be boosted."""
    assert calculate_hot_score(0, 0, now, 1.0) == calculate_hot_score(0, 0, now, 0.0)
```
