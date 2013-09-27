import re
from zope.interface import Interface
from zope.interface import implements
from zope.component import adapts
from zope.component import getMultiAdapter
try:
    from zope.component.hooks import getSite
except ImportError:
    from zope.app.component.hooks import getSite

from DateTime import DateTime
from Products.CMFCore.utils import getToolByName
from AccessControl import getSecurityManager
from Acquisition import aq_inner

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .interfaces import IPlonesocialActivitystreamLayer
from .interfaces import IActivityProvider
from plonesocial.activitystream.interfaces import IActivity

TAGRE = re.compile('(#(\S+))')

from plonesocial.activitystream.integration import PLONESOCIAL
from AccessControl import Unauthorized
import itertools
from zExceptions import NotFound
def date_key(item):
    if hasattr(item, 'effective'):
        # catalog brain
        return max(item.effective, item.created)
    # Activity
    return item.date







def link_tags(text, url=''):
    return TAGRE.sub('<a href="%s/@@stream/tag/\\2">\\1</a>' % url, text)


class ActivityProvider(object):
    """Helper for rendering IActivity
    """
    implements(IActivityProvider)
    adapts(IActivity, IPlonesocialActivitystreamLayer, Interface)

    index = ViewPageTemplateFile("templates/activity_provider.pt")

    def __init__(self, context, request, view):
        self.context = context
        self.request = request
        self.view = self.__parent__ = view

        # inline rendering
        self.microblog_context = PLONESOCIAL.context(context.context.getObject())

    def update(self):
        pass

    def render(self):
        return self.index()

    __call__ = render

    def is_anonymous(self):
        portal_membership = getToolByName(getSite(),
                                          'portal_membership',
                                          None)
        return portal_membership.isAnonymousUser()

    def can_review(self):
        """Returns true if current user has the 'Review comments' permission.
        """
        return getSecurityManager(
        ).checkPermission('Review comments',
                          aq_inner(self.context.context))

    @property
    def mtool(self):
        return getToolByName(getSite(), 'portal_membership')

    # IActivityProvider

    @property
    def author_home_url(self):
        if self.userid is None:
            return None
        else:
            portal_state = getMultiAdapter((self.context, self.request),
                                           name=u'plone_portal_state')
            url = portal_state.portal_url()
            return "%s/author/%s" % (url, self.userid)

    @property
    def user_data(self):
        return self.mtool.getMemberInfo(self.userid)

    @property
    def user_portrait(self):
        """Mugshot."""
        return self.mtool.getPersonalPortrait(self.userid)

    @property
    def date(self):
        return self._format_time(self.raw_date)

    def _format_time(self, time):
        # We have to transform Python datetime into Zope DateTime
        # before we can call toLocalizedTime.
        if hasattr(time, 'isoformat'):
            zope_time = DateTime(time.isoformat())
        else:
            # already a Zope DateTime
            zope_time = time
        util = getToolByName(getSite(), 'translation_service')
        if DateTime().Date() == zope_time.Date():
            return util.toLocalizedTime(zope_time,
                                        long_format=True,
                                        time_only=True)
        else:
            # time_only=False still returns time only
            return util.toLocalizedTime(zope_time,
                                        long_format=True)

    # IActivity

    @property
    def url(self):
        site_properties = getToolByName(self.context,
                                        "portal_properties").site_properties
        if self.portal_type in site_properties.typesUseViewActionInListings:
            return self.context.url + '/view'
        else:
            return self.context.url

    @property
    def title(self):
        return self.context.title

    @property
    def userid(self):
        return self.context.userid

    @property
    def Creator(self):
        return self.user_data and self.user_data['fullname'] or self.userid

    @property
    def text(self):
        portal_state = getMultiAdapter((self.context, self.request),
                                       name=u'plone_portal_state')
        url = portal_state.portal_url()
        return link_tags(self.context.text, url)

    @property
    def raw_date(self):
        return self.context.raw_date

    @property
    def portal_type(self):
        return self.context.portal_type

    @property
    def render_type(self):
        return self.context.render_type

    @property
    def is_status(self):
        return self.context.is_status

    @property
    def is_discussion(self):
        return self.context.is_discussion

    @property
    def is_content(self):
        return self.context.is_content

    # extra

    @property
    def getText(self):
        return self.text

    @property
    def getURL(self):
        return self.url

    @property
    def Title(self):
        return self.title



    # return inners

    def _activities_statuses(self):
#        if not self.show_microblog:
#            return []
        container = PLONESOCIAL.microblog
        # show_microblog yet no container can happen on microblog uninstall
        if not container:
            return []
        try:
            # filter on users OR context, not both
            #if self.users:
            #    # support plonesocial.network integration
            #    return container.user_values(self.users,
            #                                 limit=self.count,
            #                                 tag=self.tag)
            #elif self.microblog_context:
            if self.microblog_context:
                # support collective.local integration
                return container.context_values(self.microblog_context,
                                                limit=10,
                                                tag=None)
            else:
                # default implementation
                return container.values(limit=10,
                                        tag=None)
        except Unauthorized:
            return []

    def activities(self):
        statuses = self._activities_statuses()
        items = itertools.chain(statuses)
        # see date_key sorting function above
        items = sorted(items, key=date_key, reverse=True)

        i = 0
        for item in items:
            if i >= 10:
                break
            try:
                activity = IActivity(item)
            except Unauthorized:
                continue
            except NotFound:
                #logger.exception("NotFound: %s" % item.getURL())
                continue

            #if self._activity_visible(activity):
            if True:
                yield activity
                i += 1

    def activity_providers(self):
        for activity in self.activities():

            #if not self.can_view(activity):
                # discussion parent inaccessible
            #    continue
            yield getMultiAdapter(
                (activity, self.request, self.view),
                IActivityProvider,
                name="plonesocial.activitystream.activity_provider")

