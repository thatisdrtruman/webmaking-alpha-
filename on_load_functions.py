def load_ps_cache(PS):
	"""
	loads all rows from the PersistentStorage database table as key, value pairs

	:returns: dictionary
	"""

	dic = {}
	for item in PS.query.all():
		dic[item.id] = item.content
	return dic
