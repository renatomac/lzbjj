from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from crm.models import Member
from .authorize_net import AuthorizeNetClient, get_member_payment_status


@api_view(['POST'])
@permission_classes([AllowAny])
def authorize_net_verify_transaction(request):
    """Verify an Authorize.Net transaction by id and return member payment status."""
    transaction_id = (request.data or {}).get('transaction_id')
    member_id = (request.data or {}).get('member_id')

    if not transaction_id:
        return Response({'error': 'transaction_id is required'}, status=400)

    member = Member.objects.filter(id=member_id).first() if member_id else None
    client = AuthorizeNetClient()
    result = client.get_transaction_details(str(transaction_id))

    payload = {
        'transaction_id': transaction_id,
        'authorize_net': result,
        'member': None,
    }

    if member:
        payload['member'] = get_member_payment_status(member, transaction_id=transaction_id)

    return Response(payload)


@api_view(['GET'])
@permission_classes([AllowAny])
def authorize_net_member_status(request, member_id):
    """Return member membership and payment verification status for a member."""
    member = Member.objects.filter(id=member_id).first()
    if not member:
        return Response({'error': 'Member not found'}, status=404)

    return Response(get_member_payment_status(member))


@api_view(['POST'])
@permission_classes([AllowAny])
def authorize_net_capture_payment(request):
    """Placeholder endpoint for future create-transaction integration."""
    return Response({
        'status': 'not_implemented',
        'message': 'This endpoint will be used for future Authorize.Net capture/charge operations.',
        'created_at': timezone.now().isoformat(),
    }, status=501)
