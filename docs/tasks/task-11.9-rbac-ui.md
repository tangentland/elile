# Task 11.9: RBAC User Interface

**Priority**: P1
**Phase**: 11 - User Interfaces
**Estimated Effort**: 2 days
**Dependencies**: Task 11.1 (HR Portal API)

## Context

Create user interface for role-based access control management with role definition, permission assignment, and user management.

## Objectives

1. Role management UI
2. Permission assignment
3. User role mapping
4. Access review
5. Audit trail viewing

## Technical Approach

```python
# src/elile/api/routes/rbac.py
@router.post("/roles")
async def create_role(
    role: RoleCreate,
    current_user: User = Depends(require_admin)
) -> Role:
    # Create role
    # Assign permissions
    # Audit log
    pass
```

## Implementation Checklist

- [ ] Create RBAC APIs
- [ ] Add role management UI
- [ ] Test permissions

## Success Criteria

- [ ] Intuitive role management
- [ ] Permissions enforced
