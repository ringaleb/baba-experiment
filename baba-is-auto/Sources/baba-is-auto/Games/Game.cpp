// Copyright (c) 2020-2026 Chris Ohk

// I am making my contributions/submissions to this project solely in our
// personal capacity and am not conveying any rights to any intellectual
// property of any third parties.

#include <baba-is-auto/Games/Game.hpp>

namespace baba_is_auto
{
Game::Game(std::string_view filename)
{
    m_map.Load(filename);

    ParseRules();

    m_playState = PlayState::PLAYING;
}

void Game::Reset()
{
    m_map.Reset();

    ParseRules();

    m_playState = PlayState::PLAYING;
}

Map& Game::GetMap()
{
    return m_map;
}

const Map& Game::GetMap() const
{
    return m_map;
}

RuleManager& Game::GetRuleManager()
{
    return m_ruleManager;
}

PlayState Game::GetPlayState() const
{
    return m_playState;
}

ObjectType Game::GetPlayerIcon() const
{
    return m_playerIcon;
}

void Game::MovePlayer(Direction dir)
{
    auto positions = GetMap().GetPositions(m_playerIcon);

    for (auto& [x, y] : positions)
    {
        if (CanMove(x, y, dir))
        {
            ProcessMove(x, y, dir, m_playerIcon);
        }
    }

    ParseRules();
    CheckPlayState();
}

void Game::ParseRules()
{
    m_ruleManager.ClearRules();

    const std::size_t width = m_map.GetWidth();
    const std::size_t height = m_map.GetHeight();

    for (std::size_t y = 0; y < height; ++y)
    {
        for (std::size_t x = 0; x < width; ++x)
        {
            m_map.At(x, y).isRule = false;
        }
    }

    for (std::size_t y = 0; y < height; ++y)
    {
        for (std::size_t x = 0; x < width; ++x)
        {
            ParseRule(x, y, RuleDirection::HORIZONTAL);
            ParseRule(x, y, RuleDirection::VERTICAL);
        }
    }

    m_playerIcon = m_ruleManager.FindPlayer();

    ApplyNounIsNoun();
}

void Game::ParseRule(std::size_t x, std::size_t y, RuleDirection direction)
{
    const std::size_t width = m_map.GetWidth();
    const std::size_t height = m_map.GetHeight();

    if (direction == RuleDirection::HORIZONTAL)
    {
        if (x + 2 >= width)
        {
            return;
        }

        if (m_map.At(x, y).HasNounType() && m_map.At(x + 1, y).HasVerbType() &&
            (m_map.At(x + 2, y).HasNounType() ||
             m_map.At(x + 2, y).HasPropertyType()))
        {
            m_ruleManager.AddRule(
                { m_map.At(x, y), m_map.At(x + 1, y), m_map.At(x + 2, y) });

            m_map.At(x, y).isRule = true;
            m_map.At(x + 1, y).isRule = true;
            m_map.At(x + 2, y).isRule = true;
        }
    }
    else if (direction == RuleDirection::VERTICAL)
    {
        if (y + 2 >= height)
        {
            return;
        }

        if (m_map.At(x, y).HasNounType() && m_map.At(x, y + 1).HasVerbType() &&
            (m_map.At(x, y + 2).HasNounType() ||
             m_map.At(x, y + 2).HasPropertyType()))
        {
            m_ruleManager.AddRule(
                { m_map.At(x, y), m_map.At(x, y + 1), m_map.At(x, y + 2) });

            m_map.At(x, y).isRule = true;
            m_map.At(x, y + 1).isRule = true;
            m_map.At(x, y + 2).isRule = true;
        }
    }
}

bool Game::CanMove(std::size_t x, std::size_t y, Direction dir)
{
    int _x = static_cast<int>(x);
    int _y = static_cast<int>(y);

    const auto width = static_cast<int>(m_map.GetWidth());
    const auto height = static_cast<int>(m_map.GetHeight());

    int dx = 0, dy = 0;
    if (dir == Direction::UP)
    {
        dy = -1;
    }
    else if (dir == Direction::DOWN)
    {
        dy = 1;
    }
    else if (dir == Direction::LEFT)
    {
        dx = -1;
    }
    else if (dir == Direction::RIGHT)
    {
        dx = 1;
    }

    _x += dx;
    _y += dy;

    // Check boundary
    if (_x < 0 || _x >= width || _y < 0 || _y >= height)
    {
        return false;
    }

    const std::vector<ObjectType> types = m_map.At(_x, _y).GetTypes();

    // Check the icon has property 'STOP'.
    if (m_ruleManager.HasProperty(types, ObjectType::STOP))
    {
        return false;
    }

    if (m_ruleManager.HasProperty(types, ObjectType::PUSH) ||
        m_map.At(_x, _y).HasTextType())
    {
        if (!CanMove(_x, _y, dir))
        {
            return false;
        }
    }

    return true;
}

void Game::ProcessMove(std::size_t x, std::size_t y, Direction dir,
                       ObjectType type)
{
    int _x = static_cast<int>(x);
    int _y = static_cast<int>(y);

    int dx = 0, dy = 0;
    if (dir == Direction::UP)
    {
        dy = -1;
    }
    else if (dir == Direction::DOWN)
    {
        dy = 1;
    }
    else if (dir == Direction::LEFT)
    {
        dx = -1;
    }
    else if (dir == Direction::RIGHT)
    {
        dx = 1;
    }

    _x += dx;
    _y += dy;

    const std::vector<ObjectType> types = m_map.At(_x, _y).GetTypes();

    // MELT moving into HOT cell: destroy mover.
    // PUSH on the HOT object overrides — it gets pushed instead.
    if (m_ruleManager.HasProperty({ type }, ObjectType::MELT))
    {
        for (auto dt : types)
        {
            if (!IsTextType(dt) &&
                m_ruleManager.HasProperty({ dt }, ObjectType::HOT) &&
                !m_ruleManager.HasProperty({ dt }, ObjectType::PUSH))
            {
                m_map.RemoveObject(x, y, type);
                return;
            }
        }
    }

    // HOT moving into MELT cell: destroy MELT objects at destination.
    // PUSH on the MELT object overrides — it gets pushed instead.
    if (m_ruleManager.HasProperty({ type }, ObjectType::HOT))
    {
        for (auto dt : types)
        {
            if (!IsTextType(dt) &&
                m_ruleManager.HasProperty({ dt }, ObjectType::MELT) &&
                !m_ruleManager.HasProperty({ dt }, ObjectType::PUSH))
            {
                m_map.RemoveObject(_x, _y, dt);
            }
        }
    }

    if (m_ruleManager.HasProperty(types, ObjectType::PUSH))
    {
        auto rules = m_ruleManager.GetRules(ObjectType::PUSH);

        for (auto& rule : rules)
        {
            const ObjectType nounType = std::get<0>(rule.objects).GetTypes()[0];
            ProcessMove(_x, _y, dir, ConvertTextToIcon(nounType));
        }
    }
    else if (m_ruleManager.HasProperty(types, ObjectType::SINK))
    {
        m_map.RemoveObject(x, y, type);
        auto sinkRules = m_ruleManager.GetRules(ObjectType::SINK);
        for (auto& rule : sinkRules)
        {
            if (!std::get<2>(rule.objects).HasType(ObjectType::SINK))
                continue;
            const ObjectType nounType = std::get<0>(rule.objects).GetTypes()[0];
            m_map.RemoveObject(_x, _y, ConvertTextToIcon(nounType));
        }
        return;
    }
    else if (m_ruleManager.HasProperty(types, ObjectType::DEFEAT))
    {
        m_map.RemoveObject(x, y, type);
        return;
    }
    else if (m_map.At(_x, _y).HasTextType())
    {
        ProcessMove(_x, _y, dir, types[0]);
    }

    m_map.AddObject(_x, _y, type);
    m_map.RemoveObject(x, y, type);
}

void Game::ApplyNounIsNoun()
{
    struct Transform
    {
        std::size_t x, y;
        ObjectType from, to;
    };
    std::vector<Transform> transforms;

    for (auto& rule : m_ruleManager.GetAllRules())
    {
        const ObjectType type0 = std::get<0>(rule.objects).GetTypes()[0];
        const ObjectType type2 = std::get<2>(rule.objects).GetTypes()[0];
        if (!IsNounType(type0) || !IsNounType(type2) || type0 == type2)
            continue;

        const ObjectType iconFrom = ConvertTextToIcon(type0);
        const ObjectType iconTo   = ConvertTextToIcon(type2);

        for (auto& [px, py] : m_map.GetPositions(iconFrom))
        {
            transforms.push_back({ px, py, iconFrom, iconTo });
        }
    }

    for (auto& t : transforms)
        m_map.RemoveObject(t.x, t.y, t.from);
    for (auto& t : transforms)
        m_map.AddObject(t.x, t.y, t.to);
}

void Game::CheckPlayState()
{
    // Objects simultaneously HOT and MELT destroy themselves when rules change
    for (std::size_t y = 0; y < m_map.GetHeight(); ++y)
    {
        for (std::size_t x = 0; x < m_map.GetWidth(); ++x)
        {
            for (auto t : m_map.At(x, y).GetTypes())
            {
                if (!IsTextType(t) &&
                    m_ruleManager.HasProperty({ t }, ObjectType::HOT) &&
                    m_ruleManager.HasProperty({ t }, ObjectType::MELT))
                {
                    m_map.RemoveObject(x, y, t);
                }
            }
        }
    }

    const auto youRules = m_ruleManager.GetRules(ObjectType::YOU);
    if (youRules.empty())
    {
        m_playState = PlayState::LOST;
        return;
    }

    auto positions = m_map.GetPositions(m_playerIcon);
    if (positions.empty())
    {
        m_playState = PlayState::LOST;
        return;
    }

    auto winRules = m_ruleManager.GetRules(ObjectType::WIN);
    for (auto& pos : positions)
    {
        for (auto& rule : winRules)
        {
            const ObjectType type = std::get<0>(rule.objects).GetTypes()[0];

            if (m_map.At(pos.first, pos.second)
                    .HasType(ConvertTextToIcon(type)))
            {
                m_playState = PlayState::WON;
            }
        }
    }
}
}  // namespace baba_is_auto