def retrieve(g, notice, investigation=None):
    rows = g.query('''MATCH (m:MemoryEpisode) WHERE m.verified=true AND m.outdated=false
                      AND m.cause=$cause AND m.allergen=$allergen AND m.supplier=$supplier
                      RETURN properties(m) ORDER BY m.at DESC LIMIT 8''',
                   {'cause': 'undeclared_allergen', 'allergen': notice['allergen'], 'supplier': notice['supplier']}, investigation)
    return [{**r[0], 'applicability': 'Same supplier, allergen and causal mechanism; procedural guidance only.',
             'reused': 'Trace exact lots and independently validate packaging.',
             'rejected': 'Prior batch conclusions and approvals do not authorize this incident.'} for r in rows]
