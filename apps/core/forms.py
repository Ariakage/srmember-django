from django import forms
from martor.widgets import AdminMartorWidget, MartorWidget

from .models import BioProfile


class IsolatedMartorWidget(MartorWidget):
    class Media:
        extend = False
        css = {
            'all': (
                'plugins/css/ace.min.css',
                'plugins/css/highlight.min.css',
                'martor/css/martor.tailwind.min.css',
            )
        }
        js = (
            'plugins/js/jquery.min.js',
            'plugins/js/ace.js',
            'plugins/js/mode-markdown.js',
            'plugins/js/ext-language_tools.js',
            'plugins/js/theme-github.js',
            'plugins/js/highlight.min.js',
            'plugins/js/emojis.min.js',
            'martor/js/martor.tailwind.min.js',
        )


class BioProfileForm(forms.ModelForm):
    markdown = forms.CharField(required=False, widget=IsolatedMartorWidget(attrs={'rows': 24}))

    class Meta:
        model = BioProfile
        fields = ('markdown',)


class BioProfileAdminForm(forms.ModelForm):
    markdown = forms.CharField(required=False, widget=AdminMartorWidget(attrs={'rows': 24}))

    class Meta:
        model = BioProfile
        fields = '__all__'
