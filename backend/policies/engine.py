"""Safety constraints are deterministic and independent of language model output."""
RELEASE_PREREQUISITES = {'supplier_reconciliation', 'label_review', 'quality_review', 'relabeling_validation'}


def classify(exposures, declared, allergen):
    if allergen in declared:
        return 'unaffected', 'Historical packaging declares the notified allergen.'
    if any(x['consumption'] == 'confirmed' and x['notice'] == 'confirmed' for x in exposures):
        return 'confirmed', 'Exact notified lot consumed; historical packaging omits the allergen.'
    if exposures:
        return 'uncertain', 'Potential lot exposure; consumption or supplier scope remains unresolved.'
    return 'unaffected', 'Historical consumed lots fall outside this notice scope.'


def requires_hold(classification):
    return classification in {'confirmed', 'uncertain'}


def validate_disposition(role, decision, classification, evidence, reason):
    if role != 'QA':
        raise PermissionError('Only the simulated QA authority may decide a disposition.')
    if len(reason.strip()) < 10:
        raise ValueError('A specific decision rationale of at least 10 characters is required.')
    if decision in {'reject', 'request_evidence'}:
        return
    if decision == 'release':
        if classification == 'uncertain':
            raise ValueError('Unresolved lot exposure cannot be released. Resolve source evidence and reinvestigate first.')
        missing = RELEASE_PREREQUISITES - set(evidence)
        if missing:
            raise ValueError('Missing QA prerequisites: ' + ', '.join(sorted(missing)))
    elif decision == 'dispose':
        if 'quality_review' not in evidence:
            raise ValueError('Disposal requires a recorded quality_review attestation.')
    else:
        raise ValueError('Unsupported disposition')
